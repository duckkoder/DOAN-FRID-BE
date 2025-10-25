# app/schemas/student_attendance.py

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class StudentAttendanceImageSchema(BaseModel):
    """Schema for a single attendance image (evidence)."""
    id: int
    file_id: Optional[int] = None
    file_url: Optional[str] = Field(None, description="Public URL to the evidence image.")
    captured_at: datetime

class StudentAttendanceRecordDetailSchema(BaseModel):
    """Detailed schema for a single attendance record."""
    id: int
    session_id: int
    class_id: int = Field(..., description="ID of the class associated with the session.")
    class_name: str = Field(..., description="Name of the class associated with the session.")
    session_name: Optional[str] = Field(None, description="Name of the attendance session.")
    start_time: datetime = Field(..., description="Start time of the attendance session.")
    end_time: Optional[datetime] = Field(None, description="End time of the attendance session.")
    student_id: int
    status: str = Field(..., description="Attendance status (e.g., 'present', 'absent', 'late', 'excused').")
    confidence_score: Optional[float] = Field(None, description="Confidence score if attendance was recorded by AI.")
    recorded_at: Optional[datetime] = Field(None, description="Timestamp when the attendance was recorded.")
    notes: Optional[str] = Field(None, description="Any notes related to the attendance record.")
    images: List[StudentAttendanceImageSchema] = Field(default_factory=list, description="List of evidence images for this record.")

class StudentAttendanceSessionSummarySchema(BaseModel):
    """Summary of a student's attendance for a specific session."""
    session_id: int
    session_name: Optional[str] = Field(None, description="Name of the attendance session.")
    start_time: datetime = Field(..., description="Start time of the attendance session.")
    end_time: Optional[datetime] = Field(None, description="End time of the attendance session.")
    day_of_week: Optional[int] = Field(None, description="Day of week (0=Sunday, 1=Monday, ..., 6=Saturday).")
    period_range: Optional[str] = Field(None, description="Period range (e.g., '1-3' or '6-7').")
    class_id: int = Field(..., description="ID of the class associated with the session.")
    class_name: str = Field(..., description="Name of the class associated with the session.")
    session_status: str = Field(..., description="Status of the attendance session (e.g., 'scheduled', 'ongoing', 'finished').")
    student_attendance_status: Optional[str] = Field(None, description="Student's attendance status for this session.")
    student_recorded_at: Optional[datetime] = Field(None, description="Timestamp when student's attendance was recorded.")
    student_confidence_score: Optional[float] = Field(None, description="Confidence score of student's attendance.")
    has_evidence_images: bool = Field(False, description="True if there are evidence images for this attendance record.")

class StudentClassAttendanceSummary(BaseModel):
    """Summary of a student's attendance for a specific class."""
    class_id: int
    class_name: str
    day_of_week: Optional[int] = Field(None, description="Day of week (0=Sunday, 1=Monday, ..., 6=Saturday).")
    period_range: Optional[str] = Field(None, description="Period range (e.g., '1-3' or '6-7').")
    total_sessions: int = Field(..., description="Total number of sessions for this class.")
    attended_sessions: int = Field(..., description="Total sessions where the student was marked 'present' or 'late'.")
    absent_sessions: int = Field(..., description="Total sessions where the student was marked 'absent'.")
    late_sessions: int = Field(..., description="Total sessions where the student was marked 'late'.")
    attendance_rate: float = Field(..., description="Attendance rate in percentage for this class.")
    sessions: List[StudentAttendanceSessionSummarySchema] = Field(default_factory=list, description="List of detailed session attendance summaries.")

class StudentAttendanceReportResponse(BaseModel):
    """Overall attendance report for a student across all classes."""
    student_id: int
    student_full_name: str
    overall_attendance_rate: float = Field(..., description="Overall attendance rate across all enrolled classes.")
    classes_summary: List[StudentClassAttendanceSummary] = Field(default_factory=list, description="List of attendance summaries per class.")
