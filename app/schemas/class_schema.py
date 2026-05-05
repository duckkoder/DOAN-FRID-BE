from pydantic import BaseModel, Field, field_validator, model_validator
from typing import Optional, Dict, List, Any
from datetime import datetime


class DaySchedule(BaseModel):
    day: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    periods: List[int] = Field(..., description="List of periods (1-12)")
    location: Optional[str] = Field(None, max_length=255, description="Location for this specific session")
    room: Optional[str] = Field(None, max_length=255, description="Legacy alias for location")

    @field_validator('periods')
    @classmethod
    def validate_periods(cls, v):
        if not v:
            raise ValueError("Periods list cannot be empty")
        for p in v:
            if p < 1 or p > 12:
                raise ValueError(f"Period must be between 1 and 12, got {p}")
        return sorted(v)

    @model_validator(mode='after')
    def normalize_location(self):
        if self.location is None and self.room:
            self.location = self.room
        return self


class ScheduleModel(BaseModel):
    """Weekly schedule with day index and period numbers."""
    schedules: List[DaySchedule] = Field(..., description="List of day schedules")

    @model_validator(mode='after')
    def check_at_least_one_day(self):
        """Ensure at least one day has schedule."""
        if not self.schedules:
            raise ValueError("Schedule must have at least one day with periods")
        return self


class DeleteWithPasswordRequest(BaseModel):
    """Request to delete a resource requiring password verification."""
    password: str = Field(..., description="User's password for verification")


class CreateClassRequest(BaseModel):
    """Request to create a new class - based on Class model."""
    class_name: str = Field(..., max_length=255, description="Class name")
    teacher_id: int = Field(..., description="Teacher ID from teachers table")
    course_id: Optional[str] = Field(None, description="Course UUID")
    description: Optional[str] = Field(None, max_length=255, description="Class description")
    schedule: ScheduleModel = Field(..., description="Weekly schedule with location per session (stored in class_schedules)")

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
                    "description": "Advanced Java Programming Course",
                    "schedule": {
                        "schedules": [
                            {"day": 0, "periods": [1, 2, 3], "location": "A101"},
                            {"day": 2, "periods": [6, 7, 8], "location": "LAB2"}
                        ]
                    }
                }
            ]
        }
    }


class UpdateClassRequest(BaseModel):
    """Request to update a class."""
    class_name: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=255)
    is_active: Optional[bool] = None
    schedule: Optional[ScheduleModel] = None

    @model_validator(mode='after')
    def validate_schedule_if_provided(self):
        """If schedule is provided, ensure it's not empty."""
        if self.schedule is not None:
            if not getattr(self.schedule, 'schedules', []):
                raise ValueError("If schedule is provided, it must have at least one day with periods")
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "class_name": "Java Programming Advanced - Updated",
                    "description": "Updated description",
                    "schedule": {
                        "schedules": [
                            {"day": 0, "periods": [1, 2, 3], "location": "A101"},
                            {"day": 2, "periods": [6, 7, 8], "location": "LAB2"}
                        ]
                    }
                }
            ]
        }
    }

class UpdateClassCourseRequest(BaseModel):
    """Request to update a class's course."""
    course_id: str = Field(..., description="Course UUID")


class ClassResponse(BaseModel):
    """Basic class response."""
    id: int
    class_name: str = Field(..., alias="className")
    class_code: str = Field(..., alias="classCode")
    teacher_id: int = Field(..., alias="teacherId")
    course_id: Optional[str] = Field(None, alias="courseId")
    description: Optional[str] = None
    is_active: bool = Field(..., alias="isActive")
    created_at: datetime = Field(..., alias="createdAt")
    updated_at: Optional[datetime] = Field(None, alias="updatedAt")

    model_config = {
        "from_attributes": True,
        "populate_by_name": True
    }

class StudentClassResponse(BaseModel):
    """Student class response."""
    id: int
    class_name: str = Field(..., alias="className")
    class_code: str = Field(..., alias="classCode")
    teacher_name: str = Field(..., alias="teacherName")
    course_id: Optional[str] = Field(None, alias="courseId")
    description: Optional[str] = None
    schedule: ScheduleModel = Field(..., alias="schedule")
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
    status: str  # "active" or "inactive"
    classCode: str = Field(..., alias="classCode")
    courseId: Optional[str] = Field(None, alias="courseId")
    description: Optional[str]

    model_config = {"populate_by_name": True}


class GetClassDetailsResponse(BaseModel):
    """Response for GET /teacher/classes/{classId}."""
    success: bool = True
    data: Dict[str, Any]


class GetStudentClassesListResponse(BaseModel):
    """Response for GET /student/classes."""
    success: bool = True
    data: Dict[str, Any]


class GetStudentClassDetailsResponse(BaseModel):
    """Response for GET /student/classes/{classId}."""
    success: bool = True
    data: Dict[str, Any]


class JoinClassRequest(BaseModel):
    """Request to join a class using class code."""
    class_code: str = Field(..., min_length=9, max_length=9, description="9-character class code")
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "class_code": "ABC123XYZ"
                }
            ]
        }
    }


class JoinClassResponse(BaseModel):
    """Response for POST /student/classes/join."""
    success: bool = True
    data: Dict[str, Any]
    message: str = "Joined class successfully"


class StudentDetailInClass(BaseModel):
    """Detailed student info in class with personal information."""
    id: int  # student.id
    studentId: str = Field(..., alias="studentId")  # student.student_code
    fullName: str = Field(..., alias="fullName")  # user.full_name
    email: str  # user.email
    phone: Optional[str] = None  # user.phone
    avatar: Optional[str] = None  # user.avatar
    dateOfBirth: Optional[str] = Field(None, alias="dateOfBirth")  # student.date_of_birth
    department: Optional[str] = None  # department.name
    academicYear: Optional[str] = Field(None, alias="academicYear")  # student.academic_year
    isVerified: bool = Field(..., alias="isVerified")  # student.is_verified
    joinedAt: str = Field(..., alias="joinedAt")  # class_member.joined_at
    attendanceStats: Optional[Dict] = Field(None, alias="attendanceStats")  # Attendance statistics
    
    model_config = {"populate_by_name": True}


class ClassStudentsDetailResponse(BaseModel):
    """Response for GET /teacher/classes/{classId}/students/details."""
    success: bool = True
    data: Dict[str, Any]
    
    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "success": True,
                    "data": {
                        "class": {
                            "id": 1,
                            "className": "Java Programming",
                            "classCode": "ABC123XYZ",
                            "totalStudents": 25
                        },
                        "students": [
                            {
                                "id": 10,
                                "studentId": "SV001",
                                "fullName": "Nguyen Van A",
                                "email": "student1@example.com",
                                "phone": "0123456789",
                                "avatar": "https://...",
                                "dateOfBirth": "2002-01-15",
                                "department": "Computer Science",
                                "academicYear": "2023-2024",
                                "isVerified": True,
                                "joinedAt": "2024-09-01T10:00:00Z",
                                "attendanceStats": {
                                    "totalSessions": 20,
                                    "presentCount": 18,
                                    "absentCount": 2,
                                    "lateCount": 1,
                                    "attendanceRate": 90.0
                                }
                            }
                        ],
                        "summary": {
                            "totalStudents": 25,
                            "verifiedStudents": 23,
                            "unverifiedStudents": 2,
                            "averageAttendanceRate": 85.5
                        }
                    }
                }
            ]
        }
    }