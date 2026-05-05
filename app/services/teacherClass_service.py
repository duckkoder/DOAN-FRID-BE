"""Service for class operations - based on Class, ClassSchedule, ClassMember models."""
from datetime import datetime
from typing import Dict, Optional, List
import random
import string
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.schemas.class_schema import CreateClassRequest, UpdateClassRequest
from app.models.class_model import Class
from app.models.class_schedule import ClassSchedule
from app.models.class_member import ClassMember
from app.models.room import Room
from app.models.course import Course
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.user import User
from app.models.department import Department  # ✅ Add this
from app.models.attendance_record import AttendanceRecord  # ✅ Add this
from app.models.attendance_session import AttendanceSession  # ✅ Add this
from app.services.file_service import FileService  # ✅ Add this


class TeacherClassService:

    @staticmethod
    def _normalize_schedule_entries(schedule_payload: Dict) -> List[Dict]:
        """Normalize schedule payload into a list of day/session entries."""
        schedules = schedule_payload.get("schedules", [])
        if not isinstance(schedules, list):
            return []

        def _split_consecutive(periods: List[int]) -> List[List[int]]:
            if not periods:
                return []
            sorted_periods = sorted(set(periods))
            groups: List[List[int]] = []
            current = [sorted_periods[0]]
            for p in sorted_periods[1:]:
                if p == current[-1] + 1:
                    current.append(p)
                else:
                    groups.append(current)
                    current = [p]
            groups.append(current)
            return groups

        normalized_entries: List[Dict] = []
        for entry in schedules:
            if not isinstance(entry, dict):
                continue

            normalized_entry = dict(entry)
            if not normalized_entry.get("location") and normalized_entry.get("room"):
                normalized_entry["location"] = normalized_entry["room"]
            normalized_entry.pop("room", None)

            periods = normalized_entry.get("periods") or []
            location = normalized_entry.get("location")
            day = normalized_entry.get("day")

            if day is None or not periods:
                continue

            for group in _split_consecutive(periods):
                normalized_entries.append({
                    "day": day,
                    "periods": group,
                    "location": location,
                })

        return normalized_entries

    @staticmethod
    def _build_schedule_model(schedule_rows: List[ClassSchedule]) -> Dict:
        """Build API schedule model from multiple ClassSchedule rows."""
        schedules = []
        for row in sorted(schedule_rows, key=lambda item: ((item.schedule_data or {}).get("day", 0), item.id)):
            data = row.schedule_data or {}
            schedules.append({
                "day": data.get("day"),
                "periods": data.get("periods", []),
                "location": row.location,
            })
        return {"schedules": schedules}

    @staticmethod
    def _periods_overlap(left: List[int], right: List[int]) -> bool:
        return bool(set(left) & set(right))
    
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
        query = db.query(ClassSchedule).join(Class).filter(
            Class.teacher_id == teacher_id,
            Class.is_active == True
        )

        if exclude_class_id:
            query = query.filter(Class.id != exclude_class_id)

        existing_schedules = query.all()
        new_schedules = TeacherClassService._normalize_schedule_entries(new_schedule)

        for new_day_schedule in new_schedules:
            day = new_day_schedule["day"]
            new_periods = new_day_schedule["periods"]

            for existing_schedule in existing_schedules:
                existing_data = existing_schedule.schedule_data or {}
                if existing_data.get("day") != day:
                    continue

                existing_periods = existing_data.get("periods", [])
                if TeacherClassService._periods_overlap(new_periods, existing_periods):
                    conflict_periods = sorted(list(set(new_periods) & set(existing_periods)))
                    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    day_name = day_names[day] if 0 <= day <= 6 else f"Day {day}"

                    return (
                        True,
                        f"Schedule conflict on {day_name} with class '{existing_schedule.class_rel.class_name}' "
                        f"(Code: {existing_schedule.class_rel.class_code}). Overlapping periods: {conflict_periods}"
                    )

        return False, ""

    @staticmethod
    def check_location_conflict(
        db: Session,
        location: str,
        new_schedule: Dict,
        exclude_class_id: Optional[int] = None
    ) -> tuple[bool, str]:
        """Check if a room is already occupied at the same time."""
        if not location:
            return False, ""

        query = db.query(ClassSchedule).join(Class).filter(
            ClassSchedule.location == location,
            Class.is_active == True
        )

        if exclude_class_id:
            query = query.filter(Class.id != exclude_class_id)

        existing_schedules = query.all()
        new_schedules = TeacherClassService._normalize_schedule_entries(new_schedule)

        for new_day_schedule in new_schedules:
            day = new_day_schedule["day"]
            new_periods = new_day_schedule["periods"]

            for existing_schedule in existing_schedules:
                existing_data = existing_schedule.schedule_data or {}
                if existing_data.get("day") != day:
                    continue

                existing_periods = existing_data.get("periods", [])
                if TeacherClassService._periods_overlap(new_periods, existing_periods):
                    conflict_periods = sorted(list(set(new_periods) & set(existing_periods)))
                    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
                    day_name = day_names[day] if 0 <= day <= 6 else f"Day {day}"

                    return (
                        True,
                        f"Room '{location}' is already occupied on {day_name} by class '{existing_schedule.class_rel.class_name}' (Code: {existing_schedule.class_rel.class_code}). "
                        f"Overlapping periods: {conflict_periods}"
                    )
        
        return False, ""
    

    @staticmethod
    async def create_class(db: Session, user, payload: CreateClassRequest) -> Dict:
        """
        Create a new class with schedule.
        
        Models used:
        - Class: class_name, class_code, teacher_id, description, location, is_active
        - ClassSchedule: class_id, schedule_data (JSON), location (FK rooms.name)
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
        schedule_entries = TeacherClassService._normalize_schedule_entries(payload.schedule.model_dump(exclude_none=True)) if payload.schedule else []

        for entry in schedule_entries:
            location = entry.get("location")
            if not location:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Each schedule entry must include a location"
                )

            room_exists = db.query(Room).filter(Room.name == location, Room.status == "active").first()
            if not room_exists:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Room '{location}' does not exist or is inactive"
                )

        if schedule_entries:
            has_conflict, conflict_msg = TeacherClassService.check_schedule_conflict(
                db, teacher.id, {"schedules": schedule_entries}
            )
            if has_conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=conflict_msg)

            for entry in schedule_entries:
                has_conflict, conflict_msg = TeacherClassService.check_location_conflict(
                    db, entry["location"], {"schedules": [entry]}
                )
                if has_conflict:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=conflict_msg)
        
        # Generate unique random class_code (9 chars: letters + numbers)
        class_code = TeacherClassService.generate_class_code(db, max_length=9)
        
        course_uuid = None
        if payload.course_id:
            from uuid import UUID
            try:
                course_uuid = UUID(payload.course_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="course_id must be a valid UUID"
                )

            course = db.query(Course).filter(
                Course.id == course_uuid,
                Course.teacher_id == teacher.id
            ).first()
            if not course:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course not found or not owned by teacher"
                )

        # Create Class record
        new_class = Class(
            class_name=payload.class_name,
            class_code=class_code,
            teacher_id=payload.teacher_id,
            course_id=course_uuid,
            description=payload.description,
            is_active=True
        )
        db.add(new_class)
        db.flush()
        
        # Create one ClassSchedule row per session/day
        for entry in schedule_entries:
            class_schedule = ClassSchedule(
                class_id=new_class.id,
                schedule_data={"day": entry["day"], "periods": entry["periods"]},
                location=entry["location"]
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
            # Get schedules from ClassSchedule rows
            schedule_rows = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == cls.id
            ).all()
            schedule_data = TeacherClassService._build_schedule_model(schedule_rows) if schedule_rows else None
            
            # Count students from ClassMember
            student_count = db.query(ClassMember).filter(
                ClassMember.class_id == cls.id
            ).count()
            
            classes_data.append({
                "id": cls.id,
                "name": cls.class_name,
                "subject": cls.class_name,
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
        
        # Get ClassSchedule rows and aggregate into ScheduleModel
        schedule_rows = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == cls.id
        ).all()
        schedule_data = TeacherClassService._build_schedule_model(schedule_rows) if schedule_rows else None
        
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
                    "schedule": schedule_data,
                    "status": "active" if cls.is_active else "inactive",
                    "classCode": cls.class_code,
                    "courseId": str(cls.course_id) if cls.course_id else None,
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
        
        # Get current schedule rows for conflict checking
        schedule_rows = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == cls.id
        ).all()

        if payload.schedule is not None:
            new_schedule_entries = TeacherClassService._normalize_schedule_entries(
                payload.schedule.model_dump(exclude_none=True)
            )
        else:
            new_schedule_entries = [
                {
                    "day": (row.schedule_data or {}).get("day"),
                    "periods": (row.schedule_data or {}).get("periods", []),
                    "location": row.location,
                }
                for row in schedule_rows
                if (row.schedule_data or {}).get("day") is not None
            ]

        if new_schedule_entries:
            has_conflict, conflict_msg = TeacherClassService.check_schedule_conflict(
                db, teacher.id, {"schedules": new_schedule_entries}, exclude_class_id=class_id
            )
            if has_conflict:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=conflict_msg)

            for entry in new_schedule_entries:
                location = entry.get("location")
                if not location:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Each schedule entry must include a location")

                room_exists = db.query(Room).filter(Room.name == location, Room.status == "active").first()
                if not room_exists:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Room '{location}' does not exist or is inactive")

                has_conflict, conflict_msg = TeacherClassService.check_location_conflict(
                    db, location, {"schedules": [entry]}, exclude_class_id=class_id
                )
                if has_conflict:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=conflict_msg)
        
        # Update Class fields
        if payload.class_name is not None:
            cls.class_name = payload.class_name
        if payload.description is not None:
            cls.description = payload.description

        if payload.is_active is not None:
            cls.is_active = payload.is_active
        
        cls.updated_at = datetime.utcnow()
        
        # Update ClassSchedule rows
        if payload.schedule is not None:
            db.query(ClassSchedule).filter(ClassSchedule.class_id == cls.id).delete(synchronize_session=False)
            for entry in new_schedule_entries:
                db.add(ClassSchedule(
                    class_id=cls.id,
                    schedule_data={"day": entry["day"], "periods": entry["periods"]},
                    location=entry["location"]
                ))
        
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
    async def update_class_course(db: Session, user, class_id: int, payload: any) -> Dict:
        """Update the course of a class."""
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can update classes")
        
        cls = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
        if not cls:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")
            
        if payload.course_id == "":
            cls.course_id = None
        else:
            from uuid import UUID
            try:
                course_uuid = UUID(payload.course_id)
            except ValueError:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid course UUID")
            course = db.query(Course).filter(Course.id == course_uuid, Course.teacher_id == teacher.id).first()
            if not course:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Course not found or not owned by teacher")
            cls.course_id = course_uuid
            
        cls.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(cls)
        
        return {
            "success": True,
            "data": {
                "class": {
                    "id": cls.id,
                    "courseId": str(cls.course_id) if cls.course_id else None,
                    "updatedAt": cls.updated_at.isoformat() + "Z"
                }
            },
            "message": "Class course updated successfully"
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

    @staticmethod
    async def restore_class(db: Session, user, class_id: int) -> Dict:
        """Restore - set is_active=True."""
        
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can restore classes"
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
        
        # Restore
        cls.is_active = True
        cls.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Class reactivated successfully"
        }
    
    @staticmethod
    async def get_class_students_details(
        db: Session,
        user,
        class_id: int
    ) -> Dict:
        """
        Get detailed information of all students in a class (Teacher only).
        
        Includes:
        - Personal information (name, email, phone, avatar, date_of_birth)
        - Academic information (student_code, department, academic_year)
        - Class enrollment info (joined_at)
        - Attendance statistics
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can access student details"
            )
        
        # Verify class exists and belongs to teacher
        cls = db.query(Class).filter(
            Class.id == class_id,
            Class.teacher_id == teacher.id
        ).first()
        
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found or you don't have permission to access it"
            )
        
        # Get all class members with student and user info
        class_members = db.query(ClassMember).filter(
            ClassMember.class_id == class_id
        ).all()
        
        students_data = []
        total_attendance_rate = 0.0
        verified_count = 0
        
        for member in class_members:
            # Get student
            student = db.query(Student).filter(Student.id == member.student_id).first()
            if not student:
                continue
            
            # Get user info
            user_info = db.query(User).filter(User.id == student.user_id).first()
            if not user_info:
                continue
            
            # Get department info
            department_name = None
            if student.department_id:
                department = db.query(Department).filter(Department.id == student.department_id).first()
                department_name = department.name if department else None
            
            # ✅ Calculate attendance statistics - JOIN through AttendanceSession
            attendance_records = db.query(AttendanceRecord).join(
                AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
            ).filter(
                AttendanceSession.class_id == class_id,
                AttendanceRecord.student_id == student.id
            ).all()
            
            total_sessions = len(attendance_records)
            present_count = sum(1 for record in attendance_records if record.status == "present")
            absent_count = sum(1 for record in attendance_records if record.status == "absent")
            excused_count = sum(1 for record in attendance_records if record.status == "excused")
            attendance_rate = (present_count + excused_count) / total_sessions * 100 if total_sessions > 0 else 0.0
            
            total_attendance_rate += attendance_rate
            
            if student.is_verified:
                verified_count += 1
            
            # Get avatar URL if exists
            avatar_url = user_info.avatar_url
            
            students_data.append({
                "id": student.id,
                "studentId": student.student_code,
                "fullName": user_info.full_name,
                "email": user_info.email,
                "phone": user_info.phone,
                "avatar": avatar_url,
                "dateOfBirth": student.date_of_birth.isoformat() if student.date_of_birth else None,
                "department": department_name,
                "academicYear": student.academic_year,
                "isVerified": student.is_verified,
                "joinedAt": member.joined_at.isoformat() + "Z",
                "attendanceStats": {
                    "totalSessions": total_sessions,
                    "presentCount": present_count,
                    "absentCount": absent_count,
                    "excusedCount": excused_count,  # ✅ Added excused count
                    "attendanceRate": round(attendance_rate, 2)
                }
            })
        
        # Calculate summary statistics
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
                    "totalSessions": max(
                        (db.query(AttendanceSession).filter(
                            AttendanceSession.class_id == class_id
                        ).count()), 0
                    ),
                    "verifiedStudents": verified_count,
                    "unverifiedStudents": total_students - verified_count,
                    "averageAttendanceRate": round(average_attendance_rate, 2)
                }
            }
        }