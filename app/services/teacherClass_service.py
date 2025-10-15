"""Service for class operations - based on Class, ClassSchedule, ClassMember models."""
from datetime import datetime
from typing import Dict, Optional, Set
import random
import string
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.schemas.class_schema import CreateClassRequest, UpdateClassRequest
from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
from app.models.class_member import ClassMember
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.user import User


class TeacherClassService:
    
    @staticmethod
    def generate_class_code(db: Session, max_length: int = 9) -> str:
        """Generate random unique class code with letters and numbers."""
        while True:
            # Generate random string: uppercase letters + digits
            characters = string.ascii_uppercase + string.digits
            class_code = ''.join(random.choices(characters, k=max_length))
            
            # Check if exists in database
            existing = db.query(Class).filter(Class.class_code == class_code).first()
            if not existing:
                return class_code
    
    @staticmethod
    def check_schedule_conflict(
        db: Session,
        teacher_id: int,
        new_schedule: Dict,
        exclude_class_id: Optional[int] = None
    ) -> tuple[bool, str]:
        """
        Check if new schedule conflicts with existing teacher's schedules.
        
        Returns:
            (has_conflict: bool, conflict_message: str)
        """
        # Get all active classes of the teacher
        query = db.query(Class).filter(
            Class.teacher_id == teacher_id,
            Class.is_active == True
        )
        
        # Exclude current class if updating
        if exclude_class_id:
            query = query.filter(Class.id != exclude_class_id)
        
        existing_classes = query.all()
        
        # Check each existing class schedule
        for cls in existing_classes:
            schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).first()
            
            if not schedule or not schedule.schedule_data:
                continue
            
            # Check for conflicts day by day
            for day, new_periods in new_schedule.items():
                if not new_periods:
                    continue
                
                existing_periods = schedule.schedule_data.get(day, [])
                if not existing_periods:
                    continue
                
                # Convert period strings to sets of period numbers
                new_period_set = set()
                for period_range in new_periods:
                    start, end = map(int, period_range.split('-'))
                    new_period_set.update(range(start, end + 1))
                
                existing_period_set = set()
                for period_range in existing_periods:
                    start, end = map(int, period_range.split('-'))
                    existing_period_set.update(range(start, end + 1))
                
                # Check for overlap
                overlap = new_period_set & existing_period_set
                if overlap:
                    conflict_periods = sorted(list(overlap))
                    return (
                        True,
                        f"Schedule conflict on {day.capitalize()} with class '{cls.class_name}' "
                        f"(Code: {cls.class_code}). Overlapping periods: {conflict_periods}"
                    )
        
        return False, ""
    
    @staticmethod
    def check_location_conflict(
        db: Session,
        location: str,
        new_schedule: Dict,
        exclude_class_id: Optional[int] = None
    ) -> tuple[bool, str]:
        """
        Check if location (room) is already occupied at the same time.
        
        Returns:
            (has_conflict: bool, conflict_message: str)
        """
        if not location:
            return False, ""
        
        # Get all active classes with same location
        query = db.query(Class).filter(
            Class.location == location,
            Class.is_active == True
        )
        
        # Exclude current class if updating
        if exclude_class_id:
            query = query.filter(Class.id != exclude_class_id)
        
        existing_classes = query.all()
        
        # Check each existing class schedule
        for cls in existing_classes:
            schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).first()
            
            if not schedule or not schedule.schedule_data:
                continue
            
            # Check for conflicts day by day
            for day, new_periods in new_schedule.items():
                if not new_periods:
                    continue
                
                existing_periods = schedule.schedule_data.get(day, [])
                if not existing_periods:
                    continue
                
                # Convert period strings to sets of period numbers
                new_period_set = set()
                for period_range in new_periods:
                    start, end = map(int, period_range.split('-'))
                    new_period_set.update(range(start, end + 1))
                
                existing_period_set = set()
                for period_range in existing_periods:
                    start, end = map(int, period_range.split('-'))
                    existing_period_set.update(range(start, end + 1))
                
                # Check for overlap
                overlap = new_period_set & existing_period_set
                if overlap:
                    conflict_periods = sorted(list(overlap))
                    
                    # Get teacher name
                    teacher = db.query(Teacher).filter(Teacher.id == cls.teacher_id).first()
                    teacher_user = db.query(User).filter(User.id == teacher.user_id).first() if teacher else None
                    teacher_name = teacher_user.full_name if teacher_user else "Unknown"
                    
                    return (
                        True,
                        f"Room '{location}' is already occupied on {day.capitalize()} "
                        f"by class '{cls.class_name}' (Teacher: {teacher_name}, Code: {cls.class_code}). "
                        f"Overlapping periods: {conflict_periods}"
                    )
        
        return False, ""
    
    @staticmethod
    async def create_class(db: Session, user, payload: CreateClassRequest) -> Dict:
        """
        Create a new class with schedule.
        
        Models used:
        - Class: class_name, class_code, teacher_id, description, location, is_active
        - ClassSchedule: class_id, schedule_data (JSON)
        """
        
        # Verify teacher exists
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can create classes"
            )
        
        # Verify teacher_id matches
        if payload.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only create classes for yourself"
            )
        
        # Check for schedule conflicts
        if payload.schedule:
            schedule_dict = payload.schedule.model_dump(exclude_none=True)
            schedule_dict = {k: v for k, v in schedule_dict.items() if v}
            
            if schedule_dict:
                # Check teacher schedule conflict
                has_conflict, conflict_msg = TeacherClassService.check_schedule_conflict(
                    db, teacher.id, schedule_dict
                )
                if has_conflict:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=conflict_msg
                    )
                
                # Check location conflict
                if payload.location:
                    has_conflict, conflict_msg = TeacherClassService.check_location_conflict(
                        db, payload.location, schedule_dict
                    )
                    if has_conflict:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail=conflict_msg
                        )
        
        # Generate unique random class_code (9 chars: letters + numbers)
        class_code = TeacherClassService.generate_class_code(db, max_length=9)
        
        # Create Class record
        new_class = Class(
            class_name=payload.class_name,
            class_code=class_code,
            teacher_id=payload.teacher_id,
            description=payload.description,
            location=payload.location,
            is_active=True
        )
        db.add(new_class)
        db.flush()
        
        # Create ClassSchedule if provided
        if payload.schedule:
            schedule_dict = payload.schedule.model_dump(exclude_none=True)
            schedule_dict = {k: v for k, v in schedule_dict.items() if v}
            
            if schedule_dict:
                class_schedule = ClassSchedule(
                    class_id=new_class.id,
                    schedule_data=schedule_dict
                )
                db.add(class_schedule)
        
        db.commit()
        db.refresh(new_class)
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": new_class.id,
                    "className": new_class.class_name,
                    "teacherId": new_class.teacher_id,
                    "classCode": new_class.class_code,
                    "createdAt": new_class.created_at.isoformat() + "Z"
                }
            },
            "message": "Class created successfully"
        }
    
    @staticmethod
    async def get_classes_list(
        db: Session,
        user,
        status_filter: Optional[str] = None
    ) -> Dict:
        """
        Get all classes for teacher (no pagination).
        
        Joins:
        - Class
        - ClassSchedule (for schedule_data)
        - ClassMember (count students)
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can view classes"
            )
        
        # Build query
        query = db.query(Class).filter(Class.teacher_id == teacher.id)
        
        # Apply is_active filter
        if status_filter:
            if status_filter == "active":
                query = query.filter(Class.is_active == True)
            elif status_filter == "inactive":
                query = query.filter(Class.is_active == False)
        
        # Get all classes ordered by created_at desc
        classes = query.order_by(Class.created_at.desc()).all()
        
        # Build response
        classes_data = []
        for cls in classes:
            # Get schedule from ClassSchedule
            schedule_data = None
            schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).first()
            if schedule:
                schedule_data = schedule.schedule_data
            
            # Count students from ClassMember
            student_count = db.query(ClassMember).filter(
                ClassMember.class_id == cls.id
            ).count()
            
            classes_data.append({
                "id": cls.id,
                "name": cls.class_name,
                "location": cls.location,
                "status": "active" if cls.is_active else "inactive",
                "classCode": cls.class_code,
                "studentCount": student_count,
                "schedule": schedule_data,
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
        Get detailed information of a class.
        
        Joins:
        - Class
        - ClassSchedule
        - ClassMember -> Student -> User
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can view class details"
            )
        
        # Get Class
        cls = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == teacher.id
        ).first()
        
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found or you don't have permission"
            )
        
        # Get teacher user info
        teacher_user = db.query(User).filter(User.id == user.id).first()
        
        # Get ClassSchedule
        schedule = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == cls.id
        ).first()
        
        # Return schedule_data as ScheduleModel (dict) instead of string
        schedule_data = None
        if schedule and schedule.schedule_data:
            schedule_data = schedule.schedule_data
        
        # Get ClassMember -> Student -> User
        members = db.query(ClassMember).filter(
            ClassMember.class_id == cls.id
        ).all()
        
        students_data = []
        for member in members:
            student = db.query(Student).filter(Student.id == member.student_id).first()
            if not student:
                continue
            
            student_user = db.query(User).filter(User.id == student.user_id).first()
            if not student_user:
                continue
            
            # TODO: Calculate from attendance_records table
            students_data.append({
                "id": student.id,
                "studentId": student.student_code,
                "fullName": student_user.full_name,
                "email": student_user.email,
                "attendanceRate": 90.0,  # Mock
                "totalSessions": 20,
                "presentCount": 18,
                "absentCount": 1,
                "lateCount": 1,
                "joinedAt": member.joined_at.isoformat() + "Z"
            })
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "subject": cls.class_name,
                    "teacher": teacher_user.full_name,
                    "teacherId": teacher_user.id,
                    "students": len(students_data),
                    "maxStudents": 30,
                    "schedule": schedule_data,  # ✅ Return ScheduleModel (dict) instead of string
                    "room": cls.location,
                    "status": "active" if cls.is_active else "inactive",
                    "classCode": cls.class_code,
                    "description": cls.description
                },
                "students": students_data,
                "attendanceStats": {
                    "totalSessions": 20,
                    "averageAttendance": 85.0,
                    "totalStudents": len(students_data)
                }
            }
        }
    
    @staticmethod
    async def update_class(
        db: Session,
        user,
        class_id: int,
        payload: UpdateClassRequest
    ) -> Dict:
        """Update Class and ClassSchedule with conflict checking."""
        
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can update classes"
            )
        
        cls = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == teacher.id
        ).first()
        
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        # Get current schedule for conflict checking
        current_schedule = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == cls.id
        ).first()
        
        check_schedule = None
        if payload.schedule is not None:
            schedule_dict = payload.schedule.model_dump(exclude_none=True)
            check_schedule = {k: v for k, v in schedule_dict.items() if v}
        elif current_schedule:
            check_schedule = current_schedule.schedule_data
        
        # Check conflicts if schedule or location is being updated
        if check_schedule:
            # Check teacher schedule conflict
            has_conflict, conflict_msg = TeacherClassService.check_schedule_conflict(
                db, teacher.id, check_schedule, exclude_class_id=class_id
            )
            if has_conflict:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=conflict_msg
                )
            
            # Check location conflict
            location_to_check = payload.location if payload.location is not None else cls.location
            if location_to_check:
                has_conflict, conflict_msg = TeacherClassService.check_location_conflict(
                    db, location_to_check, check_schedule, exclude_class_id=class_id
                )
                if has_conflict:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=conflict_msg
                    )
        
        # Update Class fields
        if payload.class_name is not None:
            cls.class_name = payload.class_name
        if payload.location is not None:
            cls.location = payload.location
        if payload.description is not None:
            cls.description = payload.description
        if payload.is_active is not None:
            cls.is_active = payload.is_active
        
        cls.updated_at = datetime.utcnow()
        
        # Update ClassSchedule
        if payload.schedule is not None:
            schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).first()
            
            schedule_dict = payload.schedule.model_dump(exclude_none=True)
            schedule_dict = {k: v for k, v in schedule_dict.items() if v}
            
            if schedule:
                schedule.schedule_data = schedule_dict
                schedule.updated_at = datetime.utcnow()
            elif schedule_dict:
                new_schedule = ClassSchedule(
                    class_id=cls.id,
                    schedule_data=schedule_dict
                )
                db.add(new_schedule)
        
        db.commit()
        db.refresh(cls)
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "className": cls.class_name,
                    "updatedAt": cls.updated_at.isoformat() + "Z"
                }
            },
            "message": "Class updated successfully"
        }
    
    @staticmethod
    async def delete_class(db: Session, user, class_id: int) -> Dict:
        """Soft delete - set is_active=False."""
        
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can delete classes"
            )
        
        cls = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == teacher.id
        ).first()
        
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        # Soft delete
        cls.is_active = False
        cls.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Class deactivated successfully"
        }