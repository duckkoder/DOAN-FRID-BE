from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime


class RegisterRequest(BaseModel):
    """Request body for user registration."""
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=6, max_length=100, description="Password (min 6 characters)")
    role: str = Field(..., description="User role: 'teacher' or 'student'")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number (optional)")
    
    # Teacher-specific
    teacher_code: Optional[str] = Field(None, max_length=50, description="Teacher code (required if role=teacher)")
    department: Optional[str] = Field(None, max_length=200, description="Department (optional for teacher)")
    
    # Student-specific
    student_code: Optional[str] = Field(None, max_length=50, description="Student code (required if role=student)")
    major: Optional[str] = Field(None, max_length=200, description="Major (optional for student)")
    academic_year: Optional[int] = Field(None, ge=2000, le=2100, description="Academic year (optional for student)")
    
    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        if v not in ['teacher', 'student']:
            raise ValueError('Role must be either "teacher" or "student"')
        return v
    
    @model_validator(mode='after')
    def validate_role_specific_fields(self):
        """Validate role-specific required fields."""
        if self.role == 'teacher' and not self.teacher_code:
            raise ValueError('teacher_code is required for teacher role')
        if self.role == 'student' and not self.student_code:
            raise ValueError('student_code is required for student role')
        return self

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "full_name": "Nguyen Van A",
                    "email": "student@example.com",
                    "password": "password123",
                    "role": "student",
                    "phone": "0123456789",
                    "student_code": "SV001",
                }
            ]
        }
    }


class UserResponse(BaseModel):
    """User information in response."""
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool
    avatar_url: Optional[str] = None
    phone: Optional[str] = None
    is_verified: bool
    created_at: datetime
    
    # Role-specific info
    teacher_code: Optional[str] = None
    department: Optional[str] = None
    student_code: Optional[str] = None
    major: Optional[str] = None
    academic_year: Optional[int] = None

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    """Response for successful registration."""
    message: str = "User registered successfully"
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    """Request body for login."""
    email: str
    password: str

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "email": "student@example.com",
                    "password": "password123"
                }
            ]
        }
    }


class LoginResponse(BaseModel):
    """Response for successful login."""
    message: str = "Login successful"
    user: UserResponse
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    """Response for token refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class LogoutRequest(BaseModel):
    """Request body for logout."""
    refresh_token: str


class LogoutResponse(BaseModel):
    """Response for logout."""
    message: str = "Logged out successfully"