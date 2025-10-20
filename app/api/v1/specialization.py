"""Specialization API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, status, Query, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.specialization import (
    SpecializationCreate,
    SpecializationUpdate,
    SpecializationResponse,
    SpecializationWithDepartment
)
from app.services.specialization_service import SpecializationService

router = APIRouter(prefix="/specializations", tags=["specializations"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("", response_model=List[SpecializationResponse])
async def get_all_specializations(
    skip: int = 0,
    limit: int = 100,
    department_id: int = Query(None, description="Filter by department ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all specializations (authenticated users).
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    - **department_id**: Optional filter by department
    """
    service = SpecializationService(db)
    
    if department_id:
        specializations = service.get_by_department(department_id)
    else:
        specializations = service.get_all(skip=skip, limit=limit)
    
    return specializations


@router.get("/{specialization_id}", response_model=SpecializationWithDepartment)
async def get_specialization(
    specialization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific specialization with department info.
    
    - **specialization_id**: Specialization ID
    """
    service = SpecializationService(db)
    specialization = service.get_with_department(specialization_id)
    return specialization


@router.post("", response_model=SpecializationResponse, status_code=status.HTTP_201_CREATED)
async def create_specialization(
    specialization_data: SpecializationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new specialization (admin only).
    
    - **name**: Specialization name
    - **code**: Specialization code (unique within department)
    - **description**: Optional description
    - **department_id**: Department ID (must exist)
    """
    service = SpecializationService(db)
    specialization = service.create(specialization_data)
    return specialization


@router.put("/{specialization_id}", response_model=SpecializationResponse)
async def update_specialization(
    specialization_id: int,
    specialization_data: SpecializationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a specialization (admin only).
    
    - **specialization_id**: Specialization ID
    - **name**: New name (optional)
    - **code**: New code (optional)
    - **description**: New description (optional)
    - **department_id**: New department ID (optional)
    """
    service = SpecializationService(db)
    specialization = service.update(specialization_id, specialization_data)
    return specialization


@router.delete("/{specialization_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_specialization(
    specialization_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a specialization (admin only).
    
    Cannot delete if specialization is assigned to teachers.
    
    - **specialization_id**: Specialization ID
    """
    service = SpecializationService(db)
    service.delete(specialization_id)
    return None
