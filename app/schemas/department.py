"""Department schemas for request/response validation."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime

if TYPE_CHECKING:
    from app.schemas.specialization import SpecializationResponse


class DepartmentBase(BaseModel):
    """Base schema for Department."""
    name: str = Field(..., min_length=1, max_length=100, description="Tên khoa/phòng ban")
    code: str = Field(..., min_length=1, max_length=20, description="Mã khoa/phòng ban")
    description: Optional[str] = Field(None, max_length=500, description="Mô tả")


class DepartmentCreate(DepartmentBase):
    """Schema for creating a new Department."""
    pass


class DepartmentUpdate(BaseModel):
    """Schema for updating a Department."""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    code: Optional[str] = Field(None, min_length=1, max_length=20)
    description: Optional[str] = Field(None, max_length=500)


class DepartmentResponse(DepartmentBase):
    """Schema for Department response."""
    id: int
    created_at: datetime
    updated_at: datetime
    
    model_config = ConfigDict(from_attributes=True)


class DepartmentWithSpecializations(DepartmentResponse):
    """Schema for Department with its Specializations."""
    specializations: List["SpecializationResponse"] = []
    
    model_config = ConfigDict(from_attributes=True)


# Resolve forward references after all models are defined
def resolve_forward_refs():
    """Resolve forward references in models."""
    from app.schemas.specialization import SpecializationResponse
    DepartmentWithSpecializations.model_rebuild()


