"""Teacher schemas for API requests and responses."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional
from datetime import datetime


class TeacherBase(BaseModel):
    """Base teacher schema."""
    department_id: Optional[int] = Field(None, description="Department ID")
    specialization_id: Optional[int] = Field(None, description="Specialization ID")


class TeacherResponse(BaseModel):
    """Teacher response schema with user info."""
    id: int
    user_id: int
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
    """Request to update teacher information (Admin)."""
    department_id: Optional[int] = Field(None, description="Department ID")
    specialization_id: Optional[int] = Field(None, description="Specialization ID")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    avatar_url: Optional[str] = Field(None, description="Avatar URL (S3)")
    is_active: Optional[bool] = Field(None, description="Active status")


class TeacherProfileUpdateRequest(BaseModel):
    """Request to update teacher own profile."""
    full_name: Optional[str] = Field(None, min_length=2, max_length=255, description="Full name")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    department_id: Optional[int] = Field(None, description="Department ID")
    specialization_id: Optional[int] = Field(None, description="Specialization ID")


class UpdateAvatarRequest(BaseModel):
    """Request to update avatar URL."""
    avatar_url: str = Field(..., description="Avatar URL (S3)")


class ChangePasswordRequest(BaseModel):
    """Request to change password (requires old password)."""
    old_password: str = Field(..., description="Current password")
    new_password: str = Field(..., min_length=8, max_length=100, description="New password (min 8 characters)")
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        from app.utils.validators import validate_password_strength
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class ChangePasswordResponse(BaseModel):
    """Response after password change."""
    success: bool
    message: str


class ResetPasswordRequest(BaseModel):
    """Request to reset user password."""
    new_password: str = Field(..., min_length=8, max_length=100, description="New password (min 8 characters)")
    
    @field_validator('new_password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        from app.utils.validators import validate_password_strength
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v


class ResetPasswordResponse(BaseModel):
    """Response after password reset."""
    success: bool
    message: str
    user_id: int
    email: str


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
