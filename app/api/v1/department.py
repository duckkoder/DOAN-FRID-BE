"""Department API endpoints."""
from typing import List
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.department import (
    DepartmentCreate,
    DepartmentUpdate,
    DepartmentResponse,
    DepartmentWithSpecializations
)
from app.services.department_service import DepartmentService

router = APIRouter(prefix="/departments", tags=["departments"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to require admin role."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return current_user


@router.get("", response_model=List[DepartmentResponse])
async def get_all_departments(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get all departments (authenticated users).
    
    - **skip**: Number of records to skip (pagination)
    - **limit**: Maximum number of records to return
    """
    service = DepartmentService(db)
    departments = service.get_all(skip=skip, limit=limit)
    return departments


@router.get("/{department_id}", response_model=DepartmentWithSpecializations)
async def get_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get a specific department with its specializations.
    
    - **department_id**: Department ID
    """
    service = DepartmentService(db)
    department = service.get_with_specializations(department_id)
    return department


@router.post("", response_model=DepartmentResponse, status_code=status.HTTP_201_CREATED)
async def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Create a new department (admin only).
    
    - **name**: Department name (unique)
    - **code**: Department code (unique)
    - **description**: Optional description
    """
    service = DepartmentService(db)
    department = service.create(department_data)
    return department


@router.put("/{department_id}", response_model=DepartmentResponse)
async def update_department(
    department_id: int,
    department_data: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update a department (admin only).
    
    - **department_id**: Department ID
    - **name**: New name (optional)
    - **code**: New code (optional)
    - **description**: New description (optional)
    """
    service = DepartmentService(db)
    department = service.update(department_id, department_data)
    return department


@router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete a department (admin only).
    
    Cannot delete if department has specializations.
    
    - **department_id**: Department ID
    """
    service = DepartmentService(db)
    service.delete(department_id)
    return None
