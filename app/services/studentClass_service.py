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
from app.models.department import Department
from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession


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

    @staticmethod
    async def get_class_students_details(db: Session, user, class_id: int) -> Dict:
        """Get detailed information of classmates for enrolled student."""
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can view class members"
            )

        member = db.query(ClassMember).filter(
            ClassMember.student_id == student.id,
            ClassMember.class_id == class_id
        ).first()
        if not member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found or you are not enrolled in this class"
            )

        cls = db.query(Class).filter(Class.id == class_id).first()
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )

        class_members = db.query(ClassMember).filter(ClassMember.class_id == class_id).all()

        students_data = []
        total_attendance_rate = 0.0
        verified_count = 0

        for class_member in class_members:
            classmate = db.query(Student).filter(Student.id == class_member.student_id).first()
            if not classmate:
                continue

            user_info = db.query(User).filter(User.id == classmate.user_id).first()
            if not user_info:
                continue

            department_name = None
            if classmate.department_id:
                department = db.query(Department).filter(Department.id == classmate.department_id).first()
                department_name = department.name if department else None

            attendance_records = db.query(AttendanceRecord).join(
                AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
            ).filter(
                AttendanceSession.class_id == class_id,
                AttendanceRecord.student_id == classmate.id
            ).all()

            total_sessions = len(attendance_records)
            present_count = sum(1 for record in attendance_records if record.status == "present")
            absent_count = sum(1 for record in attendance_records if record.status == "absent")
            excused_count = sum(1 for record in attendance_records if record.status == "excused")
            attendance_rate = (present_count + excused_count) / total_sessions * 100 if total_sessions > 0 else 0.0

            total_attendance_rate += attendance_rate
            if classmate.is_verified:
                verified_count += 1

            students_data.append({
                "id": classmate.id,
                "studentId": classmate.student_code,
                "fullName": user_info.full_name,
                "email": user_info.email,
                "phone": user_info.phone,
                "avatar": user_info.avatar_url,
                "dateOfBirth": classmate.date_of_birth.isoformat() if classmate.date_of_birth else None,
                "department": department_name,
                "academicYear": classmate.academic_year,
                "isVerified": classmate.is_verified,
                "joinedAt": class_member.joined_at.isoformat() + "Z",
                "attendanceStats": {
                    "totalSessions": total_sessions,
                    "presentCount": present_count,
                    "absentCount": absent_count,
                    "excusedCount": excused_count,
                    "attendanceRate": round(attendance_rate, 2)
                }
            })

        total_students = len(students_data)
        average_attendance_rate = total_attendance_rate / total_students if total_students > 0 else 0.0

        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "className": cls.class_name,
                    "classCode": cls.class_code,
                    "totalStudents": total_students
                },
                "students": students_data,
                "summary": {
                    "totalStudents": total_students,
                    "verifiedStudents": verified_count,
                    "unverifiedStudents": total_students - verified_count,
                    "averageAttendanceRate": round(average_attendance_rate, 2)
                }
            }
        }