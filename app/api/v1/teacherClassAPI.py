"""Teacher classes endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.class_schema import (
    CreateClassRequest,
    CreateClassResponse,
    GetClassesListResponse,
    GetClassDetailsResponse,
    UpdateClassRequest,
    ClassStudentsDetailResponse,  # ✅ Add this import
)
from app.services.teacherClass_service import TeacherClassService

router = APIRouter(prefix="/teacher/classes", tags=["Teacher Classes"])


@router.post("", response_model=CreateClassResponse, status_code=status.HTTP_201_CREATED)
async def create_class(
    payload: CreateClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a new class with schedule."""
    result = await TeacherClassService.create_class(db, current_user, payload)
    return result


@router.get("", response_model=GetClassesListResponse)
async def get_classes_list(
    status: str = Query(None, description="Filter: active|inactive"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get all classes (no pagination)."""
    result = await TeacherClassService.get_classes_list(db, current_user, status)
    return result


@router.get("/{class_id}", response_model=GetClassDetailsResponse)
async def get_class_details(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get class details with students."""
    result = await TeacherClassService.get_class_details(db, current_user, class_id)
    return result


@router.put("/{class_id}", response_model=CreateClassResponse)
async def update_class(
    class_id: int,
    payload: UpdateClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update class information."""
    result = await TeacherClassService.update_class(db, current_user, class_id, payload)
    return result


@router.delete("/{class_id}")
async def delete_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deactivate a class (soft delete)."""
    result = await TeacherClassService.delete_class(db, current_user, class_id)
    return result


@router.get("/{class_id}/students/details", response_model=ClassStudentsDetailResponse)
async def get_class_students_details(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information of all students in a class (Teacher only).

    - Requires: Teacher role, class ownership
    - Path param: class_id
    - Returns: Complete student information including:
        * Personal info (name, email, phone, avatar, date_of_birth)
        * Academic info (student_code, department, academic_year)
        * Enrollment info (joined_at, verification status)
        * Attendance statistics (sessions, attendance rate)
    """
    result = await TeacherClassService.get_class_students_details(db, current_user, class_id)
    return result