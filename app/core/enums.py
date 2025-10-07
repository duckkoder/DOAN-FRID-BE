"""Enums for the application."""
from enum import Enum


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    TEACHER = "teacher"
    STUDENT = "student"


class EmbeddingStatus(str, Enum):
    """Face embedding status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SessionStatus(str, Enum):
    """Attendance session status enumeration."""
    SCHEDULED = "scheduled"
    ONGOING = "ongoing"
    FINISHED = "finished"


class AttendanceStatus(str, Enum):
    """Attendance record status enumeration."""
    PRESENT = "present"
    ABSENT = "absent"
    LATE = "late"
    EXCUSED = "excused"


class RequestStatus(str, Enum):
    """Leave request status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
