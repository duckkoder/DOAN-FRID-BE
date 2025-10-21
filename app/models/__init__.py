"""Models module for SQLAlchemy ORM entities."""
from app.models.base import Base, BaseModel

# Import all models for Alembic detection
from app.models.user import User
from app.models.admin import Admin
from app.models.department import Department
from app.models.specialization import Specialization
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.model_config import ModelConfig
from app.models.file import File
from app.models.face_embedding import FaceEmbedding
from app.models.face_registration_request import FaceRegistrationRequest
from app.models.face_model import FaceModel
from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
from app.models.class_member import ClassMember
from app.models.attendance_session import AttendanceSession
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_image import AttendanceImage
from app.models.leave_request import LeaveRequest
from app.models.refresh_token import RefreshToken
from app.models.system_log import SystemLog
from app.models.ai_training_job import AITrainingJob

__all__ = [
    "Base",
    "BaseModel",
    "User",
    "Admin",
    "Department",
    "Specialization",
    "Teacher",
    "Student",
    "ModelConfig",
    "File",
    "FaceEmbedding",
    "FaceRegistrationRequest",
    "FaceModel",
    "Class",
    "ClassSchedule",
    "ClassMember",
    "AttendanceSession",
    "AttendanceRecord",
    "AttendanceImage",
    "LeaveRequest",
    "RefreshToken",
    "SystemLog",
    "AITrainingJob",
]