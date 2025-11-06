"""Teacher profile API endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.dependencies import get_db, get_current_user
from app.models.user import User
from app.models.teacher import Teacher
from app.models.department import Department
from app.models.specialization import Specialization
from app.schemas.teacher import (
    TeacherResponse,
    TeacherProfileUpdateRequest,
    UpdateAvatarRequest,
    ChangePasswordRequest,
    ChangePasswordResponse
)
from app.core.security import get_password_hash, verify_password

router = APIRouter(prefix="/teacher", tags=["Teacher Profile"])


@router.get("/profile", response_model=TeacherResponse)
def get_teacher_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get current teacher's profile."""
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can access this endpoint"
        )
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher profile not found"
        )
    
    # Get department and specialization names
    department_name = None
    specialization_name = None
    
    if teacher.department_id:
        department = db.query(Department).filter(Department.id == teacher.department_id).first()
        department_name = department.name if department else None
    
    if teacher.specialization_id:
        specialization = db.query(Specialization).filter(Specialization.id == teacher.specialization_id).first()
        specialization_name = specialization.name if specialization else None
    
    return TeacherResponse(
        id=teacher.id,
        user_id=teacher.user_id,
        department_id=teacher.department_id,
        specialization_id=teacher.specialization_id,
        department=department_name,
        specialization=specialization_name,
        created_at=teacher.created_at,
        updated_at=teacher.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/profile", response_model=TeacherResponse)
def update_teacher_profile(
    update_data: TeacherProfileUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current teacher's profile."""
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can access this endpoint"
        )
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher profile not found"
        )
    
    # Check if at least one field is provided
    has_update = any([
        update_data.full_name is not None,
        update_data.phone is not None,
        update_data.department_id is not None,
        update_data.specialization_id is not None
    ])
    
    if not has_update:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field must be provided for update"
        )
    
    # Update user fields
    if update_data.full_name is not None:
        current_user.full_name = update_data.full_name
    if update_data.phone is not None:
        current_user.phone = update_data.phone
    
    # Update teacher fields
    if update_data.department_id is not None:
        # Verify department exists
        department = db.query(Department).filter(Department.id == update_data.department_id).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {update_data.department_id} not found"
            )
        teacher.department_id = update_data.department_id
    
    if update_data.specialization_id is not None:
        # Verify specialization exists
        specialization = db.query(Specialization).filter(Specialization.id == update_data.specialization_id).first()
        if not specialization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Specialization with id {update_data.specialization_id} not found"
            )
        teacher.specialization_id = update_data.specialization_id
    
    db.commit()
    db.refresh(teacher)
    db.refresh(current_user)
    
    # Get department and specialization names
    department_name = None
    specialization_name = None
    
    if teacher.department_id:
        department = db.query(Department).filter(Department.id == teacher.department_id).first()
        department_name = department.name if department else None
    
    if teacher.specialization_id:
        specialization = db.query(Specialization).filter(Specialization.id == teacher.specialization_id).first()
        specialization_name = specialization.name if specialization else None
    
    return TeacherResponse(
        id=teacher.id,
        user_id=teacher.user_id,
        department_id=teacher.department_id,
        specialization_id=teacher.specialization_id,
        department=department_name,
        specialization=specialization_name,
        created_at=teacher.created_at,
        updated_at=teacher.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/avatar", response_model=TeacherResponse)
def update_teacher_avatar(
    avatar_data: UpdateAvatarRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update current teacher's avatar."""
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can access this endpoint"
        )
    
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Teacher profile not found"
        )
    
    # Update avatar URL
    current_user.avatar_url = avatar_data.avatar_url
    
    db.commit()
    db.refresh(current_user)
    db.refresh(teacher)
    
    # Get department and specialization names
    department_name = None
    specialization_name = None
    
    if teacher.department_id:
        department = db.query(Department).filter(Department.id == teacher.department_id).first()
        department_name = department.name if department else None
    
    if teacher.specialization_id:
        specialization = db.query(Specialization).filter(Specialization.id == teacher.specialization_id).first()
        specialization_name = specialization.name if specialization else None
    
    return TeacherResponse(
        id=teacher.id,
        user_id=teacher.user_id,
        department_id=teacher.department_id,
        specialization_id=teacher.specialization_id,
        department=department_name,
        specialization=specialization_name,
        created_at=teacher.created_at,
        updated_at=teacher.updated_at,
        full_name=current_user.full_name,
        email=current_user.email,
        phone=current_user.phone,
        avatar_url=current_user.avatar_url,
        is_active=current_user.is_active
    )


@router.put("/change-password", response_model=ChangePasswordResponse)
def change_teacher_password(
    password_data: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change current teacher's password."""
    if current_user.role != "teacher":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only teachers can access this endpoint"
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

