"""Specialization schemas for request/response validation."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.schemas.department import DepartmentResponse


class SpecializationBase(BaseModel):
    """Base schema for Specialization."""
    name: str = Field(..., min_length=1, max_length=100, description="Tên chuyên ngành")
    code: str = Field(..., min_length=1, max_length=20, description="Mã chuyên ngành")
    description: Optional[str] = Field(None, max_length=500, description="Mô tả")
    department_id: int = Field(..., description="ID của khoa/phòng ban")


class SpecializationCreate(SpecializationBase):
    """Schema for creating a new Specialization."""
    pass


class SpecializationUpdate(BaseModel):
    """Schema for updating a Specialization."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=500)
    department_id: Optional[int] = None


class SpecializationResponse(SpecializationBase):
    """Schema for Specialization response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class SpecializationWithDepartment(SpecializationResponse):
    """Schema for Specialization with its Department info."""
    department: "DepartmentResponse"
    
    model_config = ConfigDict(from_attributes=True)


# Resolve forward references after all models are defined
def resolve_forward_refs():
    """Resolve forward references in models."""
    from app.schemas.department import DepartmentResponse
    SpecializationWithDepartment.model_rebuild()


