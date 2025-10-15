"""Teacher service for CRUD operations."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, status

from app.models.teacher import Teacher
from app.models.user import User
from app.schemas.teacher import TeacherUpdateRequest, TeacherResponse
from app.utils.pagination import PaginationParams


class TeacherService:
    """Service class for teacher operations."""
    
    @staticmethod
    def get_teacher_list(
        db: Session,
        search: Optional[str] = None,
        department: Optional[str] = None,
        is_active: Optional[bool] = None,
        skip: int = 0,
        limit: int = 10
    ) -> dict:
        """
        Get paginated list of teachers with filters.
        
        Args:
            db: Database session
            search: Search by teacher name, email, or teacher code
            department: Filter by department
            is_active: Filter by active status
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with teachers list, pagination info, and stats
        """
        # Base query with join
        query = db.query(Teacher, User).join(User, Teacher.user_id == User.id)
        
        # Apply filters
        if search:
            search_filter = or_(
                Teacher.teacher_code.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        if department:
            query = query.filter(Teacher.department.ilike(f"%{department}%"))
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # Get total count
        total = query.count()
        
        # Get stats
        total_teachers = db.query(Teacher).count()
        active_teachers = db.query(Teacher).join(User).filter(User.is_active == True).count()
        inactive_teachers = total_teachers - active_teachers
        
        # Apply pagination
        teachers = query.order_by(Teacher.created_at.desc()).offset(skip).limit(limit).all()
        
        # Build response
        teacher_list = []
        for teacher, user in teachers:
            teacher_data = TeacherResponse(
                id=teacher.id,
                user_id=teacher.user_id,
                teacher_code=teacher.teacher_code,
                department=teacher.department,
                specialization=teacher.specialization,
                created_at=teacher.created_at,
                updated_at=teacher.updated_at,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                avatar_url=user.avatar_url,
                is_active=user.is_active
            )
            teacher_list.append(teacher_data)
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        current_page = (skip // limit) + 1 if limit > 0 else 1
        
        return {
            "total": total,
            "page": current_page,
            "page_size": limit,
            "total_pages": total_pages,
            "data": teacher_list,
            "stats": {
                "total": total_teachers,
                "active": active_teachers,
                "inactive": inactive_teachers
            }
        }
    
    @staticmethod
    def get_teacher_by_id(db: Session, teacher_id: int) -> dict:
        """
        Get teacher by ID with user info.
        
        Args:
            db: Database session
            teacher_id: Teacher ID
            
        Returns:
            Teacher information
        """
        result = db.query(Teacher, User).join(
            User, Teacher.user_id == User.id
        ).filter(Teacher.id == teacher_id).first()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        teacher, user = result
        
        teacher_data = TeacherResponse(
            id=teacher.id,
            user_id=teacher.user_id,
            teacher_code=teacher.teacher_code,
            department=teacher.department,
            specialization=teacher.specialization,
            created_at=teacher.created_at,
            updated_at=teacher.updated_at,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active
        )
        
        return {"teacher": teacher_data}
    
    @staticmethod
    def update_teacher(
        db: Session, 
        teacher_id: int, 
        update_data: TeacherUpdateRequest
    ) -> dict:
        """
        Update teacher information.
        
        Args:
            db: Database session
            teacher_id: Teacher ID
            update_data: Update data
            
        Returns:
            Updated teacher information
        """
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        user = db.query(User).filter(User.id == teacher.user_id).first()
        
        # Update teacher fields
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if field in ['department', 'specialization']:
                setattr(teacher, field, value)
            elif field in ['phone', 'is_active']:
                setattr(user, field, value)
        
        db.commit()
        db.refresh(teacher)
        db.refresh(user)
        
        teacher_data = TeacherResponse(
            id=teacher.id,
            user_id=teacher.user_id,
            teacher_code=teacher.teacher_code,
            department=teacher.department,
            specialization=teacher.specialization,
            created_at=teacher.created_at,
            updated_at=teacher.updated_at,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active
        )
        
        return {
            "message": "Teacher updated successfully",
            "teacher": teacher_data
        }
    
    @staticmethod
    def delete_teacher(db: Session, teacher_id: int) -> dict:
        """
        Delete teacher (soft delete by deactivating user).
        
        Args:
            db: Database session
            teacher_id: Teacher ID
            
        Returns:
            Success message
        """
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Teacher not found"
            )
        
        user = db.query(User).filter(User.id == teacher.user_id).first()
        user.is_active = False
        
        db.commit()
        
        return {"message": "Teacher deactivated successfully"}
