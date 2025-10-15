from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, List, Any
from datetime import datetime


class ScheduleModel(BaseModel):
    """Weekly schedule with period ranges (format: '1-3' means periods 1 to 3)."""
    monday: Optional[List[str]] = Field(default_factory=list)
    tuesday: Optional[List[str]] = Field(default_factory=list)
    wednesday: Optional[List[str]] = Field(default_factory=list)
    thursday: Optional[List[str]] = Field(default_factory=list)
    friday: Optional[List[str]] = Field(default_factory=list)
    saturday: Optional[List[str]] = Field(default_factory=list)
    sunday: Optional[List[str]] = Field(default_factory=list)
    
    @field_validator('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
    @classmethod
    def validate_periods(cls, v):
        if v is None:
            return []
        for period in v:
            if not isinstance(period, str) or '-' not in period:
                raise ValueError(f"Period must be in format '1-3', got '{period}'")
            try:
                start, end = period.split('-')
                start_num, end_num = int(start), int(end)
                if start_num < 1 or end_num > 12 or start_num > end_num:
                    raise ValueError(f"Invalid period range: {period}")
            except ValueError:
                raise ValueError(f"Invalid period format '{period}'")
        return v
    
    @model_validator(mode='after')
    def check_at_least_one_day(self):
        """Ensure at least one day has schedule."""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        has_schedule = any(
            getattr(self, day) and len(getattr(self, day)) > 0 
            for day in days
        )
        if not has_schedule:
            raise ValueError("Schedule must have at least one day with periods")
        return self


class CreateClassRequest(BaseModel):
    """Request to create a new class - based on Class model."""
    class_name: str = Field(..., max_length=255, description="Class name")
    teacher_id: int = Field(..., description="Teacher ID from teachers table")
    location: Optional[str] = Field(None, max_length=255, description="Class location/room")
    description: Optional[str] = Field(None, max_length=255, description="Class description")
    schedule: ScheduleModel = Field(..., description="Weekly schedule (required, stored in class_schedules)")

    @model_validator(mode='after')
    def validate_schedule_not_empty(self):
        """Ensure schedule is provided and not empty."""
        if not self.schedule:
            raise ValueError("Schedule is required and cannot be empty")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "class_name": "Java Programming Advanced",
                    "teacher_id": 1,
                    "location": "LAB-101",
                    "description": "Advanced Java Programming Course",
                    "schedule": {
                        "monday": ["1-3", "6-9"],
                        "wednesday": ["1-3"],
                        "friday": ["4-6"]
                    }
                }
            ]
        }
    }


class UpdateClassRequest(BaseModel):
    """Request to update a class."""
    class_name: Optional[str] = Field(None, max_length=255)
    location: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    schedule: Optional[ScheduleModel] = None

    @model_validator(mode='after')
    def validate_schedule_if_provided(self):
        """If schedule is provided, ensure it's not empty."""
        if self.schedule is not None:
            days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
            has_schedule = any(
                getattr(self.schedule, day) and len(getattr(self.schedule, day)) > 0 
                for day in days
            )
            if not has_schedule:
                raise ValueError("If schedule is provided, it must have at least one day with periods")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "class_name": "Java Programming Advanced - Updated",
                    "location": "LAB-102",
                    "description": "Updated description",
                    "schedule": {
                        "monday": ["1-3"],
                        "wednesday": ["1-3"]
                    }
                }
            ]
        }
    }


class ClassResponse(BaseModel):
    """Basic class response."""
    id: int
    class_name: str = Field(..., alias="className")
    class_code: str = Field(..., alias="classCode")
    teacher_id: int = Field(..., alias="teacherId")
    location: Optional[str] = None
    description: Optional[str] = None
    is_active: bool = Field(..., alias="isActive")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }


class CreateClassResponse(BaseModel):
    """Response for POST /teacher/classes."""
    success: bool = True
    data: Dict[str, Any]
    message: str = "Class created successfully"


class ClassListItem(BaseModel):
    """Class item in list with schedule and student count."""
    id: int
    subject: str  # Same as class_name
    name: str  # Same as class_name
    location: Optional[str] = None
    status: str  # "active" or "inactive" based on is_active
    classCode: str = Field(..., alias="classCode")
    studentCount: int = Field(default=0, alias="studentCount")
    schedule: Optional[Dict] = None  # From class_schedules.schedule_data
    createdAt: str = Field(..., alias="createdAt")
    updatedAt: Optional[str] = Field(None, alias="updatedAt")

    model_config = {"populate_by_name": True}


class PaginationData(BaseModel):
    """Pagination metadata."""
    page: int
    limit: int
    total: int
    totalPages: int = Field(..., alias="totalPages")

    model_config = {"populate_by_name": True}


class GetClassesListResponse(BaseModel):
    """Response for GET /teacher/classes."""
    success: bool = True
    data: Dict[str, Any]


class StudentInClassResponse(BaseModel):
    """Student info in class - from class_members join with students and users."""
    id: int
    studentId: str = Field(..., alias="studentId")  # student.student_code
    fullName: str = Field(..., alias="fullName")  # user.full_name
    email: str  # user.email
    attendanceRate: float = Field(..., alias="attendanceRate")
    totalSessions: int = Field(..., alias="totalSessions")
    presentCount: int = Field(..., alias="presentCount")
    absentCount: int = Field(..., alias="absentCount")
    lateCount: int = Field(..., alias="lateCount")
    joinedAt: str = Field(..., alias="joinedAt")  # class_member.joined_at

    model_config = {"populate_by_name": True}


class AttendanceStatsResponse(BaseModel):
    """Attendance statistics for a class."""
    totalSessions: int = Field(..., alias="totalSessions")
    averageAttendance: float = Field(..., alias="averageAttendance")
    totalStudents: int = Field(..., alias="totalStudents")

    model_config = {"populate_by_name": True}


class ClassDetailResponse(BaseModel):
    """Detailed class information."""
    id: int
    subject: str
    teacher: str  # user.full_name
    teacherId: int = Field(..., alias="teacherId")
    students: int  # count of class_members
    schedule: ScheduleModel  # Human-readable from class_schedules
    room: Optional[str]  # Same as location
    status: str  # "active" or "inactive"
    classCode: str = Field(..., alias="classCode")
    description: Optional[str]

    model_config = {"populate_by_name": True}


class GetClassDetailsResponse(BaseModel):
    """Response for GET /teacher/classes/{classId}."""
    success: bool = True
    data: Dict[str, Any]