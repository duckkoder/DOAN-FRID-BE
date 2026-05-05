"""API v1 router aggregation."""
from fastapi import APIRouter

from app.api.v1 import leaveRequestAPI, teacherClassAPI
from app.api.v1 import studentClassAPI
from app.api.v1 import auth, admin, files, department, specialization, attendance, face_registration
from app.api.v1 import studentDashboard
from app.api.v1 import studentAttendanceAPI
from app.api.v1 import teacher, student
from app.api.v1 import class_posts
from app.api.v1 import courses
from app.api.v1 import rooms
from app.api.v1 import documentAPI


# Create main API router
api_router = APIRouter()

# Include routers
api_router.include_router(auth.router, tags=["Authentication"])

# Include classAPI router
api_router.include_router(teacherClassAPI.router, tags=["Teacher Classes"])
api_router.include_router(studentClassAPI.router, tags=["Student Classes"])
api_router.include_router(studentDashboard.router, tags=["Student Dashboard"])
api_router.include_router(studentAttendanceAPI.router, tags=["Student Attendance"])

# Include profile routers
api_router.include_router(teacher.router, tags=["Teacher Profile"])
api_router.include_router(student.router, tags=["Student Profile"])

api_router.include_router(admin.router, tags=["Admin"])
api_router.include_router(files.router, tags=["Files"])

api_router.include_router(leaveRequestAPI.router, tags=["Leave Requests"])

# Department & Specialization routers (tags already defined in their routers)
api_router.include_router(department.router)
api_router.include_router(specialization.router)

# Include attendance router
api_router.include_router(attendance.router, tags=["Attendance"])

# Include face registration router
api_router.include_router(face_registration.router, tags=["Face Registration"])

# Include class posts router
api_router.include_router(class_posts.router)

# Include courses router (Teacher course & document management)
api_router.include_router(courses.router)

# Include rooms router
api_router.include_router(rooms.router)

# Include class documents router
api_router.include_router(documentAPI.router)

# Include RAG proxy router
from app.api.v1 import rag  # noqa: E402
api_router.include_router(rag.router)

# TODO: Import and include other routers when created
# from app.api.v1 import users, classes, attendance
# api_router.include_router(users.router, prefix="/users", tags=["Users"])
# api_router.include_router(classes.router, prefix="/classes", tags=["Classes"])
# api_router.include_router(attendance.router, prefix="/attendance", tags=["Attendance"])


@api_router.get("/health")
def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "version": "1.0.0"}
