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
    
    Các trạng thái:
    - PENDING: Chờ giáo viên xác nhận (confidence thấp < threshold)
    - PRESENT: Có mặt (được nhận diện với confidence cao hoặc đã được xác nhận)
    - ABSENT: Vắng không phép
    - EXCUSED: Vắng có phép (có đơn xin nghỉ được duyệt)
    
    KHÔNG có trạng thái LATE (đi muộn)
    """
    PENDING = "pending"  # ✅ NEW STATUS - Chờ xác nhận
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
