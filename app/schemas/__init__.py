"""Schemas module for Pydantic models (DTOs)."""
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentWithSpecializations,
)
from app.schemas.specialization import (
    SpecializationCreate,
    SpecializationUpdate,
    SpecializationResponse,
    SpecializationWithDepartment,
)

# Resolve forward references
from app.schemas.department import resolve_forward_refs as dept_resolve
from app.schemas.specialization import resolve_forward_refs as spec_resolve

dept_resolve()
spec_resolve()

__all__ = [
    "DepartmentCreate",
    "DepartmentUpdate",
    "DepartmentResponse",
    "DepartmentWithSpecializations",
    "SpecializationCreate",
    "SpecializationUpdate",
    "SpecializationResponse",
    "SpecializationWithDepartment",
]

