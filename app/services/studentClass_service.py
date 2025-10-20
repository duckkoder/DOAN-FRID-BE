"""Service for student class operations."""
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
from app.models.class_member import ClassMember
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.user import User


class StudentClassService:
    
    @staticmethod
    async def join_class(db: Session, user, class_code: str) -> Dict:
        """
        Join a class using class code.
        
        Validation:
        - Student must exist
        - Class must exist and be active
        - Student must not already be enrolled
        """
        
        # Verify student exists
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can join classes"
            )
        
        # Find class by code
        cls = db.query(Class).filter(
            Class.class_code == class_code.upper()
        ).first()
        
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found. Please check the class code"
            )
        
        # Check if class is active
        if not cls.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This class is no longer active"
            )
        
        # Check if student is already enrolled
        existing_member = db.query(ClassMember).filter(
            ClassMember.student_id == student.id,
            ClassMember.class_id == cls.id
        ).first()
        
        if existing_member:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You are already enrolled in this class"
            )
        
        # Create ClassMember
        new_member = ClassMember(
            class_id=cls.id,
            student_id=student.id,
            joined_at=datetime.utcnow()
        )
        db.add(new_member)
        db.commit()
        db.refresh(new_member)
        
        # Get teacher info for response
        teacher = db.query(Teacher).filter(Teacher.id == cls.teacher_id).first()
        teacher_user = db.query(User).filter(User.id == teacher.user_id).first() if teacher else None
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "className": cls.class_name,
                    "classCode": cls.class_code,
                    "teacherName": teacher_user.full_name if teacher_user else "Unknown",
                    "location": cls.location,
                    "description": cls.description,
                    "joinedAt": new_member.joined_at.isoformat() + "Z"
                }
            },
            "message": "Joined class successfully"
        }
    
    @staticmethod
    async def leave_class(db: Session, user, class_id: int) -> Dict:
        """
        Leave a class (remove enrollment).
        """
        
        # Verify student exists
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can leave classes"
            )
        
        # Check if student is enrolled
        member = db.query(ClassMember).filter(
            ClassMember.student_id == student.id,
            ClassMember.class_id == class_id
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="You are not enrolled in this class"
            )
        
        # Delete enrollment
        db.delete(member)
        db.commit()
        
        return {
            "success": True,
            "message": "Left class successfully"
        }
    
    @staticmethod
    async def get_student_classes(
        db: Session,
        user,
        status_filter: Optional[str] = None
    ) -> Dict:
        """
        Get list of classes that student is enrolled in.
        
        Joins:
        - Student -> ClassMember -> Class -> ClassSchedule
        - Class -> Teacher -> User (for teacher name)
        """
        
        # Verify student exists
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can view their classes"
            )
        
        # Get all class_members for this student
        query = db.query(ClassMember).filter(ClassMember.student_id == student.id)
        
        class_members = query.all()
        
        # Build response
        classes_data = []
        for member in class_members:
            # Get Class
            cls = db.query(Class).filter(Class.id == member.class_id).first()
            if not cls:
                continue
            
            # Apply status filter
            if status_filter:
                if status_filter == "active" and not cls.is_active:
                    continue
                elif status_filter == "inactive" and cls.is_active:
                    continue
            
            # Get Teacher info
            teacher = db.query(Teacher).filter(Teacher.id == cls.teacher_id).first()
            if not teacher:
                continue
            
            teacher_user = db.query(User).filter(User.id == teacher.user_id).first()
            if not teacher_user:
                continue
            
            # Get ClassSchedule
            schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).first()
            
            schedule_data = {
                "monday": [],
                "tuesday": [],
                "wednesday": [],
                "thursday": [],
                "friday": [],
                "saturday": [],
                "sunday": []
            }
            
            if schedule and schedule.schedule_data:
                # Merge with actual data
                for day, periods in schedule.schedule_data.items():
                    if day in schedule_data and periods:
                        schedule_data[day] = periods
            
            classes_data.append({
                "id": cls.id,
                "className": cls.class_name,
                "classCode": cls.class_code,
                "teacherName": teacher_user.full_name,
                "location": cls.location,
                "description": cls.description,
                "schedule": schedule_data,
                "isActive": cls.is_active,
                "createdAt": cls.created_at.isoformat() + "Z",
                "updatedAt": cls.updated_at.isoformat() + "Z" if cls.updated_at else None
            })
        
        return {
            "success": True,
            "data": {
                "classes": classes_data,
                "total": len(classes_data)
            }
        }
    
    @staticmethod
    async def get_class_details(db: Session, user, class_id: int) -> Dict:
        """
        Get detailed information of a class for student.
        
        Joins:
        - Student -> ClassMember -> Class -> ClassSchedule
        - Class -> Teacher -> User
        """
        
        # Verify student exists
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can view class details"
            )
        
        # Check if student is enrolled in this class
        member = db.query(ClassMember).filter(
            ClassMember.student_id == student.id,
            ClassMember.class_id == class_id
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found or you are not enrolled in this class"
            )
        
        # Get Class
        cls = db.query(Class).filter(Class.id == class_id).first()
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        # Get Teacher info
        teacher = db.query(Teacher).filter(Teacher.id == cls.teacher_id).first()
        teacher_user = db.query(User).filter(User.id == teacher.user_id).first() if teacher else None
        
        # Get ClassSchedule
        schedule = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == cls.id
        ).first()
        
        schedule_data = {
            "monday": [],
            "tuesday": [],
            "wednesday": [],
            "thursday": [],
            "friday": [],
            "saturday": [],
            "sunday": []
        }
        
        if schedule and schedule.schedule_data:
            for day, periods in schedule.schedule_data.items():
                if day in schedule_data and periods:
                    schedule_data[day] = periods
        
        # Count total students in class
        total_students = db.query(ClassMember).filter(
            ClassMember.class_id == class_id
        ).count()
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "className": cls.class_name,
                    "classCode": cls.class_code,
                    "teacherName": teacher_user.full_name if teacher_user else "Unknown",
                    "teacherId": teacher.id if teacher else None,
                    "location": cls.location,
                    "description": cls.description,
                    "schedule": schedule_data,
                    "isActive": cls.is_active,
                    "totalStudents": total_students,
                    "joinedAt": member.joined_at.isoformat() + "Z",
                    "createdAt": cls.created_at.isoformat() + "Z",
                    "updatedAt": cls.updated_at.isoformat() + "Z" if cls.updated_at else None
                },
                "enrollment": {
                    "joinedAt": member.joined_at.isoformat() + "Z",
                }

            }
        }