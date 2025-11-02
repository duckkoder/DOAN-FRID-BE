from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import Optional
from datetime import datetime, date


class RegisterRequest(BaseModel):
    """Request body for user registration."""
    full_name: str = Field(..., min_length=2, max_length=255, description="Full name of user")
    email: EmailStr = Field(..., description="Valid email address")
    password: str = Field(..., min_length=8, max_length=100, description="Password (min 8 characters, must contain 1 uppercase, 1 lowercase, 1 digit)")
    role: str = Field(..., description="User role: 'teacher' or 'student'")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number (optional)")
    avatar_url: Optional[str] = Field(None, description="Avatar URL (S3)")
    
    # Teacher-specific
    teacher_code: Optional[str] = Field(None, max_length=50, description="Teacher code (required if role=teacher)")
    department_id: Optional[int] = Field(None, description="Department ID (optional for teacher)")
    specialization_id: Optional[int] = Field(None, description="Specialization ID (optional for teacher)")
    
    # Student-specific
    student_code: Optional[str] = Field(None, max_length=50, description="Student code (required if role=student)")
    academic_year: Optional[int] = Field(None, ge=2000, le=2100, description="Academic year (optional for student)")
    date_of_birth: Optional[date] = Field(None, description="Date of birth (optional for student)")
    
    @field_validator('password')
    @classmethod
    def validate_password(cls, v):
        """Validate password strength."""
        from app.utils.validators import validate_password_strength
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v
    
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
                    "password": "Password123",
                    "role": "student",
                    "phone": "0123456789",
                    "student_code": "SV001",
                    "department_id": 1,
                    "academic_year": 2024
                },
                {
                    "full_name": "Teacher Name",
                    "email": "teacher@example.com",
                    "password": "Teacher123",
                    "role": "teacher",
                    "phone": "0987654321",
                    "teacher_code": "GV001",
                    "department_id": 1,
                    "specialization_id": 2
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
    teacher_id: Optional[int] = None
    teacher_code: Optional[str] = None
    department_id: Optional[int] = None
    specialization_id: Optional[int] = None
    department: Optional[str] = None  # Department name for display
    specialization: Optional[str] = None  # Specialization name for display

    student_id: Optional[int] = None
    student_code: Optional[str] = None
    department_id: Optional[int] = None  # For student
    department: Optional[str] = None  # Department name for display (for both teacher and student)
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
                    "password": "Password123"
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