"""Student schemas for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, date


class StudentBase(BaseModel):
    """Base student schema."""
    student_code: str = Field(..., max_length=20)
    department_id: Optional[int] = Field(None, description="Department ID (FK)")
    academic_year: Optional[str] = Field(None, max_length=10)
    date_of_birth: Optional[date] = None


class StudentResponse(BaseModel):
    """Student response schema with user info."""
    id: int
    user_id: int
    student_code: str
    date_of_birth: Optional[date] = None
    department_id: Optional[int] = None
    department: Optional[str] = None  # Department name for display
    academic_year: Optional[str] = None
    is_verified: bool
    created_at: datetime
    updated_at: datetime
    
    # User info
    full_name: str
    email: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    
    model_config = {"from_attributes": True}


class StudentUpdateRequest(BaseModel):
    """Request to update student information."""
    department_id: Optional[int] = Field(None, description="Department ID")
    academic_year: Optional[str] = Field(None, max_length=10, description="Academic year")
    date_of_birth: Optional[date] = Field(None, description="Date of birth")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    is_active: Optional[bool] = Field(None, description="Active status")
    is_verified: Optional[bool] = Field(None, description="Verification status")


class StudentListResponse(BaseModel):
    """Response for student list with stats."""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: list[StudentResponse]
    
    # Stats
    stats: dict = {
        "total": 0,
        "active": 0,
        "inactive": 0,
        "verified": 0,
        "unverified": 0
    }


class StudentDetailResponse(BaseModel):
    """Detailed student response."""
    student: StudentResponse
    classes: list = []  # Will be populated with class info if needed
    attendance_stats: dict = {}  # Attendance statistics
