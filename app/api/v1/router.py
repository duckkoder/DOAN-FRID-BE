"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import teacherClassAPI

from app.api.v1 import auth, admin, files, department, specialization


# Create main API router
api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, tags=["Authentication"])

# Include classAPI router
api_router.include_router(teacherClassAPI.router, tags=["Classes"])

api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(files.router, tags=["Files"])

# Department & Specialization routers (tags already defined in their routers)
api_router.include_router(department.router)
api_router.include_router(specialization.router)


# TODO: Import and include other routers when created
# from app.api.v1 import users, classes, attendance
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
# api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])


@api_router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
