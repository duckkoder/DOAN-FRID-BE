"""API v1 router aggregation."""
from fastapi import APIRouter
from app.api.v1 import auth, admin

# Create main API router
api_router = APIRouter()

# Include auth router
api_router.include_router(auth.router, tags=["Authentication"])

# Include admin router
api_router.include_router(admin.router, tags=["Admin"])

# TODO: Import and include other routers when created
# from app.api.v1 import users, classes, attendance
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
# api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])


@api_router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
