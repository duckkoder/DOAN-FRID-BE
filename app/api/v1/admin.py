"""Admin API endpoints for managing teachers, students, and system."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.teacher import TeacherListResponse, TeacherDetailResponse, TeacherUpdateRequest
from app.services.teacher_service import TeacherService
from fastapi import HTTPException


router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to check if user is admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user


@router.get(
    "/teachers",
    response_model=TeacherListResponse,
    summary="Get list of teachers",
    description="Get paginated list of teachers with filters. Admin only."
)
async def get_teachers(
    search: Optional[str] = Query(None, description="Search by name, email, or teacher code"),
    department: Optional[str] = Query(None, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get list of teachers with pagination and filters.
    
    - **search**: Search by teacher name, email, or teacher code
    - **department**: Filter by department
    - **is_active**: Filter by active status (true/false)
    - **page**: Page number (starts from 1)
    - **limit**: Number of items per page (max 100)
    """
    skip = (page - 1) * limit
    result = TeacherService.get_teacher_list(
        db=db,
        search=search,
        department=department,
        is_active=is_active,
        skip=skip,
        limit=limit
    )
    return result


@router.get(
    "/teachers/{teacher_id}",
    response_model=TeacherDetailResponse,
    summary="Get teacher by ID",
    description="Get detailed information of a specific teacher. Admin only."
)
async def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get teacher details by ID.
    
    - **teacher_id**: Teacher ID
    """
    result = TeacherService.get_teacher_by_id(db=db, teacher_id=teacher_id)
    return result


@router.put(
    "/teachers/{teacher_id}",
    summary="Update teacher information",
    description="Update teacher information. Admin only."
)
async def update_teacher(
    teacher_id: int,
    update_data: TeacherUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update teacher information.
    
    - **teacher_id**: Teacher ID
    - **update_data**: Fields to update (department, specialization, phone, is_active)
    """
    result = TeacherService.update_teacher(
        db=db,
        teacher_id=teacher_id,
        update_data=update_data
    )
    return result


@router.delete(
    "/teachers/{teacher_id}",
    summary="Delete teacher",
    description="Deactivate teacher account. Admin only."
)
async def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete (deactivate) teacher account.
    
    - **teacher_id**: Teacher ID
    """
    result = TeacherService.delete_teacher(db=db, teacher_id=teacher_id)
    return result
