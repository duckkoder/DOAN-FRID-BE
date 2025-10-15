"""Student service for CRUD operations."""
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from fastapi import HTTPException, status

from app.models.student import Student
from app.models.user import User
from app.schemas.student import StudentUpdateRequest, StudentResponse


class StudentService:
    """Service class for student operations."""
    
    @staticmethod
    def get_student_list(
        db: Session,
        search: Optional[str] = None,
        major: Optional[str] = None,
        academic_year: Optional[str] = None,
        is_active: Optional[bool] = None,
        is_verified: Optional[bool] = None,
        skip: int = 0,
        limit: int = 10
    ) -> dict:
        """
        Get paginated list of students with filters.
        
        Args:
            db: Database session
            search: Search by student name, email, or student code
            major: Filter by major
            academic_year: Filter by academic year
            is_active: Filter by active status
            is_verified: Filter by verification status
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            Dictionary with students list, pagination info, and stats
        """
        # Base query with join
        query = db.query(Student, User).join(User, Student.user_id == User.id)
        
        # Apply filters
        if search:
            search_filter = or_(
                Student.student_code.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%")
            )
            query = query.filter(search_filter)
        
        if major:
            query = query.filter(Student.major.ilike(f"%{major}%"))
        
        if academic_year:
            query = query.filter(Student.academic_year == academic_year)
        
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        if is_verified is not None:
            query = query.filter(Student.is_verified == is_verified)
        
        # Get total count
        total = query.count()
        
        # Get stats
        total_students = db.query(Student).count()
        active_students = db.query(Student).join(User).filter(User.is_active == True).count()
        inactive_students = total_students - active_students
        verified_students = db.query(Student).filter(Student.is_verified == True).count()
        unverified_students = total_students - verified_students
        
        # Apply pagination
        students = query.order_by(Student.created_at.desc()).offset(skip).limit(limit).all()
        
        # Build response
        student_list = []
        for student, user in students:
            student_data = StudentResponse(
                id=student.id,
                user_id=student.user_id,
                student_code=student.student_code,
                date_of_birth=student.date_of_birth,
                major=student.major,
                academic_year=student.academic_year,
                is_verified=student.is_verified,
                created_at=student.created_at,
                updated_at=student.updated_at,
                full_name=user.full_name,
                email=user.email,
                phone=user.phone,
                avatar_url=user.avatar_url,
                is_active=user.is_active
            )
            student_list.append(student_data)
        
        # Calculate pagination
        total_pages = (total + limit - 1) // limit if limit > 0 else 1
        current_page = (skip // limit) + 1 if limit > 0 else 1
        
        return {
            "total": total,
            "page": current_page,
            "page_size": limit,
            "total_pages": total_pages,
            "data": student_list,
            "stats": {
                "total": total_students,
                "active": active_students,
                "inactive": inactive_students,
                "verified": verified_students,
                "unverified": unverified_students
            }
        }
    
    @staticmethod
    def get_student_by_id(db: Session, student_id: int) -> dict:
        """
        Get student by ID with user info.
        
        Args:
            db: Database session
            student_id: Student ID
            
        Returns:
            Student information
        """
        result = db.query(Student, User).join(
            User, Student.user_id == User.id
        ).filter(Student.id == student_id).first()
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        student, user = result
        
        student_data = StudentResponse(
            id=student.id,
            user_id=student.user_id,
            student_code=student.student_code,
            date_of_birth=student.date_of_birth,
            major=student.major,
            academic_year=student.academic_year,
            is_verified=student.is_verified,
            created_at=student.created_at,
            updated_at=student.updated_at,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active
        )
        
        return {"student": student_data}
    
    @staticmethod
    def update_student(
        db: Session, 
        student_id: int, 
        update_data: StudentUpdateRequest
    ) -> dict:
        """
        Update student information.
        
        Args:
            db: Database session
            student_id: Student ID
            update_data: Update data
            
        Returns:
            Updated student information
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        user = db.query(User).filter(User.id == student.user_id).first()
        
        # Update student fields
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            if field in ['major', 'academic_year', 'date_of_birth', 'is_verified']:
                setattr(student, field, value)
            elif field in ['phone', 'is_active']:
                setattr(user, field, value)
        
        db.commit()
        db.refresh(student)
        db.refresh(user)
        
        student_data = StudentResponse(
            id=student.id,
            user_id=student.user_id,
            student_code=student.student_code,
            date_of_birth=student.date_of_birth,
            major=student.major,
            academic_year=student.academic_year,
            is_verified=student.is_verified,
            created_at=student.created_at,
            updated_at=student.updated_at,
            full_name=user.full_name,
            email=user.email,
            phone=user.phone,
            avatar_url=user.avatar_url,
            is_active=user.is_active
        )
        
        return {
            "message": "Student updated successfully",
            "student": student_data
        }
    
    @staticmethod
    def delete_student(db: Session, student_id: int) -> dict:
        """
        Delete student (soft delete by deactivating user).
        
        Args:
            db: Database session
            student_id: Student ID
            
        Returns:
            Success message
        """
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student not found"
            )
        
        user = db.query(User).filter(User.id == student.user_id).first()
        user.is_active = False
        
        db.commit()
        
        return {"message": "Student deactivated successfully"}
