"""Teacher schemas for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TeacherBase(BaseModel):
    """Base teacher schema."""
    teacher_code: str = Field(..., max_length=20)
    department_id: Optional[int] = Field(None, description="Department ID")
    specialization_id: Optional[int] = Field(None, description="Specialization ID")


class TeacherResponse(BaseModel):
    """Teacher response schema with user info."""
    id: int
    user_id: int
    teacher_code: str
    department_id: Optional[int] = None
    specialization_id: Optional[int] = None
    department: Optional[str] = None  # Department name for display
    specialization: Optional[str] = None  # Specialization name for display
    created_at: datetime
    updated_at: datetime
    
    # User info
    full_name: str
    email: str
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool
    
    model_config = {"from_attributes": True}


class TeacherUpdateRequest(BaseModel):
    """Request to update teacher information."""
    department_id: Optional[int] = Field(None, description="Department ID")
    specialization_id: Optional[int] = Field(None, description="Specialization ID")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    avatar_url: Optional[str] = Field(None, description="Avatar URL (S3)")
    is_active: Optional[bool] = Field(None, description="Active status")


class TeacherListResponse(BaseModel):
    """Response for teacher list with stats."""
    total: int
    page: int
    page_size: int
    total_pages: int
    data: list[TeacherResponse]
    
    # Stats
    stats: dict = {
        "total": 0,
        "active": 0,
        "inactive": 0
    }


class TeacherDetailResponse(BaseModel):
    """Detailed teacher response."""
    teacher: TeacherResponse
    classes: list = []  # Will be populated with class info if needed
