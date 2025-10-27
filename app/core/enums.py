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
    """Attendance record status enumeration.
    
    Chỉ có 3 trạng thái:
    - PRESENT: Có mặt (được nhận diện hoặc xác nhận)
    - ABSENT: Vắng không phép
    - EXCUSED: Vắng có phép (có đơn xin nghỉ được duyệt)
    
    KHÔNG có trạng thái LATE (đi muộn)
    """
    PRESENT = "present"
    ABSENT = "absent"
    EXCUSED = "excused"
    LATE = "late"  # DEPRECATED - Không sử dụng, chỉ giữ lại để tương thích database


class RequestStatus(str, Enum):
    """Leave request status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
