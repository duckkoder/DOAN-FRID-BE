"""Student classes endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.class_schema import (
    GetStudentClassesListResponse,
    GetStudentClassDetailsResponse,
    JoinClassRequest,
    JoinClassResponse
)
from app.services.studentClass_service import StudentClassService

router = APIRouter(prefix="/student/classes", tags=["Student Classes"])


@router.post("/join", response_model=JoinClassResponse, status_code=status.HTTP_201_CREATED)
async def join_class(
    payload: JoinClassRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Join a class using class code.
    
    - Requires: Student role, valid JWT token
    - Body: class_code (9 characters)
    - Returns: Class info and join confirmation
    - Errors:
        - 404: Class not found
        - 400: Class inactive or already enrolled
    """
    result = await StudentClassService.join_class(db, current_user, payload.class_code)
    return result


@router.delete("/{class_id}/leave")
async def leave_class(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Leave a class (remove enrollment).
    
    - Requires: Student role, valid JWT token
    - Path param: class_id
    - Returns: Success message
    - Errors:
        - 404: Not enrolled in this class
    """
    result = await StudentClassService.leave_class(db, current_user, class_id)
    return result


@router.get("", response_model=GetStudentClassesListResponse)
async def get_student_classes(
    status: str = Query(None, description="Filter: active|inactive"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get list of classes that student is enrolled in.
    
    - Requires: Student role, valid JWT token
    - Query params: status (optional)
    - Returns: List of enrolled classes with teacher info and schedule
    """
    result = await StudentClassService.get_student_classes(db, current_user, status)
    return result


@router.get("/{class_id}", response_model=GetStudentClassDetailsResponse)
async def get_class_details(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get detailed information of a class that student is enrolled in.
    
    - Requires: Student role, valid JWT token
    - Path param: class_id
    - Returns: Class details with schedule and enrollment info
    """
    result = await StudentClassService.get_class_details(db, current_user, class_id)
    return result