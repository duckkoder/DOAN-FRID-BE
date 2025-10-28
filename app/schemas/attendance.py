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
    day_of_week: Optional[int] = Field(None, description="Thứ trong tuần (0=Chủ nhật, 1=Thứ 2, ..., 6=Thứ 7)")
    period_range: Optional[str] = Field(None, description="Khoảng tiết học (VD: '1-3', '6-7')")
    session_index: Optional[int] = Field(None, description="Chỉ số buổi học trong ngày (0, 1, 2, ...)")


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
    day_of_week: Optional[int]
    period_range: Optional[str]
    session_index: Optional[int]
    ai_session_id: Optional[str] = Field(None, description="AI Service session ID")
    created_at: datetime
    
    class Config:
        from_attributes = True


class StartSessionWithAIResponse(BaseModel):
    """Response khi start session với AI-Service."""
    session_id: int = Field(..., description="Backend session ID")
    ai_session_id: str = Field(..., description="AI Service session ID")
    ai_ws_url: str = Field(..., description="WebSocket URL cho AI Service")
    ai_ws_token: str = Field(..., description="JWT token cho WebSocket authentication")
    expires_at: datetime = Field(..., description="Thời gian hết hạn của session")
    status: str = Field(..., description="Status của session")


class EndSessionRequest(BaseModel):
    """Request kết thúc phiên điểm danh."""
    mark_absent: bool = Field(default=True, description="Tự động đánh dấu vắng cho sinh viên chưa điểm danh")


class EndSessionResponse(BaseModel):
    """Response khi kết thúc phiên."""
    session: SessionResponse
    total_students: int
    present_count: int
    absent_count: int
    excused_count: int = Field(default=0, description="Số sinh viên vắng có phép (đã xin nghỉ được duyệt)")
    attendance_rate: float  # Chỉ tính present / total


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
    status: str  # present (luôn là present khi được nhận diện)
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


class WSStudentStatusUpdate(BaseModel):
    """Message WebSocket gửi cho sinh viên về trạng thái điểm danh của họ."""
    type: str = "student_status_update"
    session_id: int
    student_id: int
    status: str  # present, absent, excused
    confidence_score: Optional[float] = None
    message: str
    recorded_at: datetime


class WSConfirmationUpdate(BaseModel):
    """Message WebSocket khi giáo viên xác nhận điểm danh."""
    type: str = "confirmation_update"
    session_id: int
    student_id: int
    student_code: str
    full_name: str
    status: str  # present, absent, excused
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[datetime] = None


class WSSessionStatus(BaseModel):
    """Message WebSocket về trạng thái phiên."""
    type: str = "session_status"
    session_id: int
    status: str
    message: str


# ============= Teacher Confirmation Schemas =============

class ConfirmAttendanceRequest(BaseModel):
    """Request xác nhận điểm danh."""
    status: str = Field(default="present", description="present (có mặt)")
    notes: Optional[str] = Field(None, description="Ghi chú")


class RejectAttendanceRequest(BaseModel):
    """Request từ chối điểm danh."""
    reason: Optional[str] = Field(None, description="Lý do từ chối")


class ConfirmAttendanceResponse(BaseModel):
    """Response sau khi xác nhận."""
    success: bool
    record: AttendanceRecordDetail


class ConfirmAllPendingResponse(BaseModel):
    """Response sau khi xác nhận tất cả."""
    success: bool
    confirmed_count: int
    records: List[AttendanceRecordDetail]


class PendingStudentDetail(BaseModel):
    """Thông tin sinh viên chờ xác nhận."""
    record_id: int
    student_id: int
    student_code: str
    full_name: str
    confidence_score: Optional[float]
    recorded_at: datetime
    
    class Config:
        from_attributes = True


class PendingStudentsResponse(BaseModel):
    """Danh sách sinh viên chờ xác nhận."""
    pending_count: int
    students: List[PendingStudentDetail]


# ============= Student Schemas =============

class CurrentSessionResponse(BaseModel):
    """Thông tin phiên điểm danh hiện tại."""
    has_active_session: bool
    session: Optional[SessionResponse] = None
    my_attendance: Optional[AttendanceRecordDetail] = None


class MyAttendanceStatusResponse(BaseModel):
    """Trạng thái điểm danh của sinh viên."""
    student_id: int
    status: Optional[str] = None  # None nếu chưa điểm danh
    recorded_at: Optional[datetime] = None
    confirmed_at: Optional[datetime] = None
    is_ai_detected: bool = False
    confidence_score: Optional[float] = None
    message: str  # Human-readable message


# ============= Student Schemas (Simplified) =============

class StudentAttendanceStatus(BaseModel):
    """Trạng thái điểm danh của sinh viên."""
    is_present: bool
    status: str  # present, absent, excused
    recorded_at: Optional[datetime]
    confidence_score: Optional[float]


class StudentCurrentSessionResponse(BaseModel):
    """Response cho sinh viên check phiên hiện tại."""
    has_active_session: bool
    session: Optional[SessionResponse] = None
    my_status: Optional[StudentAttendanceStatus] = None


class WSStudentAttendanceUpdate(BaseModel):
    """WebSocket message gửi cho sinh viên khi được điểm danh."""
    type: str = "student_attendance_update"
    session_id: int
    student_id: int
    status: str
    recorded_at: datetime
    confidence_score: float
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


# ============= AI Service Callback Schemas =============

class AIValidatedStudent(BaseModel):
    """Thông tin sinh viên đã được AI Service validate."""
    student_code: str = Field(..., description="Mã sinh viên")
    student_name: str = Field(..., description="Tên sinh viên")
    track_id: int = Field(..., description="Tracking ID")
    avg_confidence: float = Field(..., description="Độ tin cậy trung bình")
    frame_count: int = Field(..., description="Số frame đã xử lý")
    recognition_count: int = Field(..., description="Số lần nhận diện thành công")
    validation_passed_at: datetime = Field(..., description="Thời điểm pass validation")


class AICallbackPayload(BaseModel):
    """Payload từ AI Service callback."""
    session_id: str = Field(..., description="AI session ID")
    validated_students: List[AIValidatedStudent] = Field(..., description="Danh sách sinh viên đã validate")
    timestamp: datetime = Field(..., description="Thời gian callback")


class AICallbackResponse(BaseModel):
    """Response cho AI Service callback."""
    status: str = Field(..., description="Status của callback")
    processed_students: int = Field(..., description="Số sinh viên đã xử lý")
    message: str = Field(..., description="Thông báo")
