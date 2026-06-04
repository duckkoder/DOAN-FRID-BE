"""
AI-Powered Attendance System - FastAPI Application
Main entry point for the FastAPI application.
"""
import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.v1.router import api_router
from app.api.v1.face_registration_ws import router as face_registration_ws_router
from app.core.security import decode_token
from app.platform.database import PlatformSessionLocal
from app.platform.models.tenant import Tenant
from app.platform.services import PlatformAuditLogService


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

# Create FastAPI application instance
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url=f"{settings.API_V1_STR}/docs",
    redoc_url=f"{settings.API_V1_STR}/redoc",
)


# Configure CORS
app.add_middleware(
    CORSMiddleware,
    # allow_origins=settings.ALLOWED_ORIGINS,
    allow_origins=["*"],  # Allow all origins for development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _tenant_slug_from_request(request: Request) -> str | None:
    authorization = request.headers.get("authorization") or ""
    if authorization.lower().startswith("bearer "):
        payload = decode_token(authorization.split(" ", 1)[1].strip())
        if payload and payload.get("scope") != "platform":
            tenant_slug = payload.get("tenant_slug")
            if tenant_slug:
                return str(tenant_slug)

    parts = [part for part in request.url.path.split("/") if part]
    if parts and parts[0] not in {"api", "health", "docs", "redoc", "openapi.json"}:
        return parts[0]
    return None


def _record_request_error(request: Request, status_code: int, exc: Exception | None = None) -> None:
    tenant_slug = _tenant_slug_from_request(request)
    db = PlatformSessionLocal()
    try:
        tenant = None
        if tenant_slug:
            tenant = db.query(Tenant).filter(Tenant.slug == tenant_slug).first()

        details = {
            "method": request.method,
            "path": request.url.path,
            "query": str(request.url.query or ""),
            "status_code": status_code,
            "tenant_slug": tenant_slug,
        }
        if exc:
            details.update({
                "error_type": type(exc).__name__,
                "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__, limit=12)),
            })

        PlatformAuditLogService.record(
            db,
            None,
            "tenant.error",
            status="failed",
            tenant=tenant,
            message=f"{request.method} {request.url.path} failed with {status_code}",
            details=details,
        )
    except Exception:
        logging.getLogger(__name__).exception("platform.error_log.write_failed path=%s", request.url.path)
    finally:
        db.close()


@app.middleware("http")
async def record_server_errors(request: Request, call_next):
    try:
        response = await call_next(request)
    except Exception as exc:
        _record_request_error(request, 500, exc)
        raise

    if response.status_code >= 500 and request.url.path.startswith(settings.API_V1_STR):
        _record_request_error(request, response.status_code)
    return response


# Include API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

# Include WebSocket router for face registration
app.include_router(face_registration_ws_router, prefix=settings.API_V1_STR, tags=["Face Registration WebSocket"])


# Root endpoint
@app.get("/")
def root():
    """Root endpoint - API information."""
    return {
        "message": "Welcome to AI-Powered Attendance System API",
        "version": settings.VERSION,
        "docs": f"{settings.API_V1_STR}/docs",
    }


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
    )
