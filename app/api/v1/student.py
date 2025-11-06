"""Student profile API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.student import Student
from app.models.department import Department
from app.schemas.student import (
    StudentResponse,
    StudentProfileUpdateRequest,
    UpdateAvatarRequest,
    ChangePasswordRequest,
    ChangePasswordResponse
)
from app.core.security import get_password_hash, verify_password

router = APIRouter(prefix="/student", tags=["Student Profile"])


@router.get("/profile", response_model=StudentResponse)
def get_student_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current student's profile."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint"
        )
    
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Get department name
    department_name = None
    if student.department_id:
        department = db.query(Department).filter(Department.id == student.department_id).first()
        department_name = department.name if department else None
    
    return StudentResponse(
        id=student.id,
        user_id=student.user_id,
        student_code=student.student_code,
        date_of_birth=student.date_of_birth,
        department_id=student.department_id,
        department=department_name,
        academic_year=student.academic_year,
        is_verified=student.is_verified,
        created_at=student.created_at,
        updated_at=student.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/profile", response_model=StudentResponse)
def update_student_profile(
    update_data: StudentProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current student's profile."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint"
        )
    
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Update user fields
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.phone is not None:
        current_user.phone = update_data.phone
    
    # Update student fields
    if update_data.date_of_birth is not None:
        student.date_of_birth = update_data.date_of_birth
    
    if update_data.department_id is not None:
        # Verify department exists
        department = db.query(Department).filter(Department.id == update_data.department_id).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {update_data.department_id} not found"
            )
        student.department_id = update_data.department_id
    
    if update_data.academic_year is not None:
        student.academic_year = update_data.academic_year
    
    db.commit()
    db.refresh(student)
    db.refresh(current_user)
    
    # Get department name
    department_name = None
    if student.department_id:
        department = db.query(Department).filter(Department.id == student.department_id).first()
        department_name = department.name if department else None
    
    return StudentResponse(
        id=student.id,
        user_id=student.user_id,
        student_code=student.student_code,
        date_of_birth=student.date_of_birth,
        department_id=student.department_id,
        department=department_name,
        academic_year=student.academic_year,
        is_verified=student.is_verified,
        created_at=student.created_at,
        updated_at=student.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/avatar", response_model=StudentResponse)
def update_student_avatar(
    avatar_data: UpdateAvatarRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current student's avatar."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint"
        )
    
    student = db.query(Student).filter(Student.user_id == current_user.id).first()
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Student profile not found"
        )
    
    # Update avatar URL
    current_user.avatar_url = avatar_data.avatar_url
    
    db.commit()
    db.refresh(current_user)
    db.refresh(student)
    
    # Get department name
    department_name = None
    if student.department_id:
        department = db.query(Department).filter(Department.id == student.department_id).first()
        department_name = department.name if department else None
    
    return StudentResponse(
        id=student.id,
        user_id=student.user_id,
        student_code=student.student_code,
        date_of_birth=student.date_of_birth,
        department_id=student.department_id,
        department=department_name,
        academic_year=student.academic_year,
        is_verified=student.is_verified,
        created_at=student.created_at,
        updated_at=student.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/change-password", response_model=ChangePasswordResponse)
def change_student_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current student's password."""
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access this endpoint"
        )
    
    # Verify old password
    if not verify_password(password_data.old_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect"
        )
    
    # Check if new password is different from old password
    if password_data.old_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from current password"
        )
    
    # Hash and update new password
    current_user.password_hash = get_password_hash(password_data.new_password)
    
    db.commit()
    
    return ChangePasswordResponse(
        success=True,
        message="Password changed successfully"
    )

