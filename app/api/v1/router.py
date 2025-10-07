"""API v1 router aggregation."""
from fastapi import APIRouter

# Create main API router
api_router = APIRouter()


# TODO: Import and include specific routers when created
# from app.api.v1 import auth, users, classes, attendance

# api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
# api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])


@api_router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
