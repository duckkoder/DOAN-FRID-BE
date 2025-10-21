"""Attendance schemas for request/response models."""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ============= Session Schemas =============

class StartSessionRequest(BaseModel):
    """Request để bắt đầu phiên điểm danh."""
    class_id: int = Field(..., description="ID của lớp học")
    session_name: Optional[str] = Field(None, description="Tên phiên (tùy chọn)")
    late_threshold_minutes: int = Field(default=15, description="Số phút được phép trễ")
    location: Optional[str] = Field(None, description="Địa điểm điểm danh")


class SessionResponse(BaseModel):
    """Response thông tin phiên điểm danh."""
    id: int
    class_id: int
    session_name: Optional[str]
    start_time: datetime
    end_time: Optional[datetime]
    status: str  # ongoing, finished, scheduled
    late_threshold_minutes: int
    location: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True


class EndSessionRequest(BaseModel):
    """Request kết thúc phiên điểm danh."""
    mark_absent: bool = Field(default=True, description="Tự động đánh dấu vắng cho sinh viên chưa điểm danh")


class EndSessionResponse(BaseModel):
    """Response khi kết thúc phiên."""
    session: SessionResponse
    total_students: int
    present_count: int
    late_count: int
    absent_count: int
    attendance_rate: float


# ============= Recognition Schemas =============

class DetectionInfo(BaseModel):
    """Thông tin detection của khuôn mặt."""
    bbox: List[float] = Field(..., description="Bounding box [x1, y1, x2, y2]")
    confidence: float = Field(..., description="Độ tin cậy detection")
    track_id: Optional[int] = Field(None, description="ID tracking")
    student_id: Optional[str] = Field(None, description="ID sinh viên nếu được nhận diện")
    student_code: Optional[str] = Field(None, description="Mã sinh viên")
    student_name: Optional[str] = Field(None, description="Tên sinh viên")
    recognition_confidence: Optional[float] = Field(None, description="Độ tin cậy nhận diện")


class RecognizeFrameRequest(BaseModel):
    """Request để nhận diện frame từ camera."""
    session_id: int = Field(..., description="ID của phiên điểm danh")
    image_base64: str = Field(..., description="Frame ảnh dạng base64")


class RecognizedStudent(BaseModel):
    """Thông tin sinh viên được nhận diện."""
    student_id: int
    student_code: str
    full_name: str
    status: str  # present hoặc late
    confidence_score: float
    recorded_at: datetime


class RecognizeFrameResponse(BaseModel):
    """Response sau khi nhận diện frame."""
    success: bool
    message: str
    total_faces_detected: int
    students_recognized: List[RecognizedStudent]
    processing_time_ms: float
    detections: Optional[List[DetectionInfo]] = Field(default=None, description="Thông tin detections với bbox")


# ============= Attendance Record Schemas =============

class AttendanceRecordDetail(BaseModel):
    """Chi tiết bản ghi điểm danh."""
    id: int
    session_id: int
    student_id: int
    student_code: str
    student_name: str
    status: str
    confidence_score: Optional[float]
    recorded_at: Optional[datetime]
    notes: Optional[str]
    
    class Config:
        from_attributes = True


class SessionAttendanceListResponse(BaseModel):
    """Danh sách điểm danh của phiên."""
    session: SessionResponse
    records: List[AttendanceRecordDetail]
    statistics: dict


# ============= WebSocket Messages =============

class WSAttendanceUpdate(BaseModel):
    """Message WebSocket khi có sinh viên được điểm danh."""
    type: str = "attendance_update"  # loại message
    session_id: int
    student: RecognizedStudent


class WSSessionStatus(BaseModel):
    """Message WebSocket về trạng thái phiên."""
    type: str = "session_status"
    session_id: int
    status: str
    message: str


# ============= Query Schemas =============

class GetSessionsRequest(BaseModel):
    """Request lấy danh sách phiên."""
    class_id: Optional[int] = None
    status: Optional[str] = None  # ongoing, finished, scheduled
    skip: int = 0
    limit: int = 100


class SessionListResponse(BaseModel):
    """Response danh sách phiên."""
    sessions: List[SessionResponse]
    total: int
