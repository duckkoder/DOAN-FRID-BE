"""Teacher schemas for API requests and responses."""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class TeacherBase(BaseModel):
    """Base teacher schema."""
    teacher_code: str = Field(..., max_length=20)
    department: Optional[str] = Field(None, max_length=100)
    specialization: Optional[str] = Field(None, max_length=100)


class TeacherResponse(BaseModel):
    """Teacher response schema with user info."""
    id: int
    user_id: int
    teacher_code: str
    department: Optional[str] = None
    specialization: Optional[str] = None
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
    department: Optional[str] = Field(None, max_length=100, description="Department")
    specialization: Optional[str] = Field(None, max_length=100, description="Specialization")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
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
