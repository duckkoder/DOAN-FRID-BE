"""Schemas for CSV import functionality."""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import date
import re


class StudentCSVRow(BaseModel):
    """Single student row from CSV."""
    row_number: int = Field(..., description="Row number in CSV (for error tracking)")
    full_name: str = Field(..., min_length=2, max_length=255)
    mssv: str = Field(..., description="Student code (9 digits)")
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)
    department_name: Optional[str] = Field(None, description="Department name")
    academic_year: Optional[str] = Field(None, max_length=10)
    date_of_birth: Optional[str] = Field(None, description="Format: YYYY-MM-DD or DD/MM/YYYY")
    
    # Validation results
    is_valid: bool = Field(default=True, description="Whether this row passes validation")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    
    @field_validator('mssv')
    @classmethod
    def validate_mssv_format(cls, v):
        """Validate MSSV is 9 digits."""
        if not v or not v.strip():
            raise ValueError("MSSV không được để trống")
        v = v.strip()
        if not re.match(r'^[0-9]{9}$', v):
            raise ValueError("MSSV phải là 9 chữ số")
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength."""
        from app.utils.validators import validate_password_strength
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v and v.strip():
            v = v.strip()
            # Vietnamese phone: 10 digits starting with 0
            if not re.match(r'^0\d{9}$', v):
                raise ValueError("Số điện thoại phải có 10 chữ số và bắt đầu bằng 0")
        return v
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name is not empty."""
        if not v or not v.strip():
            raise ValueError("Họ tên không được để trống")
        return v.strip()
    
    @field_validator('academic_year')
    @classmethod
    def validate_academic_year(cls, v):
        """Validate academic year is a valid 4-digit year."""
        if v and v.strip():
            v = v.strip()
            # Check if it's a 4-digit number
            if not re.match(r'^[0-9]{4}$', v):
                raise ValueError("Năm học phải là 4 chữ số (ví dụ: 2020, 2021)")
            
            # Check if year is reasonable (between 1990 and 2100)
            year = int(v)
            if year < 1990 or year > 2100:
                raise ValueError("Năm học phải từ 1990 đến 2100")
        return v
    
    @field_validator('date_of_birth')
    @classmethod
    def validate_date_of_birth(cls, v):
        """Validate date of birth format."""
        if v and v.strip():
            v = v.strip()
            # Accept YYYY-MM-DD or DD/MM/YYYY
            if not (re.match(r'^\d{4}-\d{2}-\d{2}$', v) or re.match(r'^\d{2}/\d{2}/\d{4}$', v)):
                raise ValueError("Ngày sinh phải theo định dạng YYYY-MM-DD hoặc DD/MM/YYYY")
            
            # Try to parse the date to ensure it's valid
            try:
                from datetime import datetime
                if '-' in v:
                    datetime.strptime(v, '%Y-%m-%d')
                else:
                    datetime.strptime(v, '%d/%m/%Y')
            except ValueError:
                raise ValueError("Ngày sinh không hợp lệ (ví dụ ngày 32, tháng 13)")
        return v


class TeacherCSVRow(BaseModel):
    """Single teacher row from CSV."""
    row_number: int = Field(..., description="Row number in CSV")
    full_name: str = Field(..., min_length=2, max_length=255)
    email: str = Field(..., description="Email prefix (before @dut.udn.vn)")
    password: str = Field(..., min_length=8, max_length=100)
    teacher_code: str = Field(..., max_length=50)
    phone: Optional[str] = Field(None, max_length=50)
    department_name: Optional[str] = Field(None)
    specialization_name: Optional[str] = Field(None)
    
    # Validation results
    is_valid: bool = Field(default=True, description="Whether this row passes validation")
    errors: List[str] = Field(default_factory=list, description="List of validation errors")
    
    @field_validator('email')
    @classmethod
    def validate_email_format(cls, v):
        """Validate email format."""
        if not v or not v.strip():
            raise ValueError("Email không được để trống")
        v = v.strip()
        if not re.match(r'^[a-zA-Z0-9._%+-]+$', v):
            raise ValueError("Email chỉ được chứa chữ cái, số và ký tự ._%+-")
        return v
    
    @field_validator('password')
    @classmethod
    def validate_password_strength(cls, v):
        """Validate password strength."""
        from app.utils.validators import validate_password_strength
        is_valid, error_message = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error_message)
        return v
    
    @field_validator('teacher_code')
    @classmethod
    def validate_teacher_code(cls, v):
        """Validate teacher code is not empty."""
        if not v or not v.strip():
            raise ValueError("Mã giáo viên không được để trống")
        return v.strip()
    
    @field_validator('phone')
    @classmethod
    def validate_phone(cls, v):
        """Validate phone number format."""
        if v and v.strip():
            v = v.strip()
            # Vietnamese phone: 10 digits starting with 0
            if not re.match(r'^0\d{9}$', v):
                raise ValueError("Số điện thoại phải có 10 chữ số và bắt đầu bằng 0")
        return v
    
    @field_validator('full_name')
    @classmethod
    def validate_full_name(cls, v):
        """Validate full name is not empty."""
        if not v or not v.strip():
            raise ValueError("Họ tên không được để trống")
        return v.strip()


class StudentCSVPreviewResponse(BaseModel):
    """Response for student CSV preview."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: List[StudentCSVRow]
    can_import: bool = Field(..., description="True if all rows are valid")


class TeacherCSVPreviewResponse(BaseModel):
    """Response for teacher CSV preview."""
    total_rows: int
    valid_rows: int
    invalid_rows: int
    rows: List[TeacherCSVRow]
    can_import: bool = Field(..., description="True if all rows are valid")


class CSVImportConfirmRequest(BaseModel):
    """Request to confirm CSV import after preview."""
    rows: List[dict] = Field(..., description="Valid rows to import")


class CSVImportResult(BaseModel):
    """Result of CSV import operation."""
    success: bool
    total_attempted: int
    successful: int
    failed: int
    errors: List[dict] = Field(default_factory=list, description="List of errors for failed imports")
    message: str
