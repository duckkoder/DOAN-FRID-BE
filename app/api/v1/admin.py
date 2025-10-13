"""Admin API endpoints for managing teachers, students, and system."""
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.teacher import TeacherListResponse, TeacherDetailResponse, TeacherUpdateRequest
from app.schemas.student import StudentListResponse, StudentDetailResponse, StudentUpdateRequest
from app.services.teacher_service import TeacherService
from app.services.student_service import StudentService


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


# ============================================================================
# STUDENT ENDPOINTS
# ============================================================================

@router.get(
    "/students",
    response_model=StudentListResponse,
    summary="Get list of students",
    description="Get paginated list of students with filters. Admin only."
)
async def get_students(
    search: Optional[str] = Query(None, description="Search by name, email, or student code"),
    major: Optional[str] = Query(None, description="Filter by major"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get list of students with pagination and filters.
    
    - **search**: Search by student name, email, or student code
    - **major**: Filter by major/specialization
    - **academic_year**: Filter by academic year (e.g., "2021", "2022")
    - **is_active**: Filter by active status (true/false)
    - **is_verified**: Filter by verification status (true/false)
    - **page**: Page number (starts from 1)
    - **limit**: Number of items per page (max 100)
    """
    skip = (page - 1) * limit
    result = StudentService.get_student_list(
        db=db,
        search=search,
        major=major,
        academic_year=academic_year,
        is_active=is_active,
        is_verified=is_verified,
        skip=skip,
        limit=limit
    )
    return result


@router.get(
    "/students/{student_id}",
    response_model=StudentDetailResponse,
    summary="Get student by ID",
    description="Get detailed information of a specific student. Admin only."
)
async def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get student details by ID.
    
    - **student_id**: Student ID
    """
    result = StudentService.get_student_by_id(db=db, student_id=student_id)
    return result


@router.put(
    "/students/{student_id}",
    summary="Update student information",
    description="Update student information. Admin only."
)
async def update_student(
    student_id: int,
    update_data: StudentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update student information.
    
    - **student_id**: Student ID
    - **update_data**: Fields to update (major, academic_year, date_of_birth, phone, is_active, is_verified)
    """
    result = StudentService.update_student(
        db=db,
        student_id=student_id,
        update_data=update_data
    )
    return result


@router.delete(
    "/students/{student_id}",
    summary="Delete student",
    description="Deactivate student account. Admin only."
)
async def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete (deactivate) student account.
    
    - **student_id**: Student ID
    """
    result = StudentService.delete_student(db=db, student_id=student_id)
    return result
