# app/services/student_attendance_service.py

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from fastapi import HTTPException, status

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.class_model import Class
from app.models.class_member import ClassMember
from app.models.student import Student
from app.models.user import User
from app.models.attendance_image import AttendanceImage
from app.models.file import File

from app.schemas.student_attendance import (
    StudentAttendanceImageSchema,
    StudentAttendanceRecordDetailSchema,
    StudentAttendanceSessionSummarySchema,
    StudentClassAttendanceSummary,
    StudentAttendanceReportResponse,
)
from app.services.file_service import FileService

class StudentAttendanceService:
    def __init__(self, db: Session):
        self.db = db
        self.file_service = FileService(db)

    def _get_student_id_from_user_id(self, user_id: str) -> int:
        """Helper function to get student_id from user_id."""
        student = self.db.query(Student).filter(Student.user_id == user_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for the given user."
            )
        return student.id
    
    async def get_student_class_sessions_attendance(
        self,
        user_id: str,
        class_id: int,
        session_status_filter: Optional[str] = None # Filter by session status (e.g., "scheduled", "ongoing", "finished")
    ) -> StudentClassAttendanceSummary:
        """
        Retrieves attendance status for all sessions of a specific class for a student.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        # Verify student is a member of this class
        class_member = self.db.query(ClassMember).filter(
            ClassMember.student_id == student_id,
            ClassMember.class_id == class_id
        ).first()
        if not class_member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Student is not enrolled in this class."
            )
        
        class_obj = self.db.query(Class).filter(Class.id == class_id).first()
        if not class_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found."
            )

        # Get all attendance sessions for this class
        sessions_query = self.db.query(AttendanceSession).filter(
            AttendanceSession.class_id == class_id
        )
        if session_status_filter:
            sessions_query = sessions_query.filter(AttendanceSession.status == session_status_filter)

        sessions = sessions_query.order_by(AttendanceSession.start_time.desc()).all()

        sessions_summary_list: List[StudentAttendanceSessionSummarySchema] = []
        attended_sessions_count = 0 # Includes present and late
        absent_sessions_count = 0
        late_sessions_count = 0
        total_class_sessions = len(sessions)

        for session in sessions:
            record = self.db.query(AttendanceRecord).filter(
                AttendanceRecord.session_id == session.id,
                AttendanceRecord.student_id == student_id
            ).first()

            student_attendance_status = record.status if record else None
            student_recorded_at = record.recorded_at if record else None
            student_confidence_score = record.confidence_score if record else None
            has_evidence_images = False
            if record:
                images_count = self.db.query(AttendanceImage).filter(
                    AttendanceImage.attendance_record_id == record.id
                ).count()
                if images_count > 0:
                    has_evidence_images = True

            # Update counts for summary
            if student_attendance_status == "present":
                attended_sessions_count += 1
            elif student_attendance_status == "late":
                late_sessions_count += 1
                attended_sessions_count += 1 # Late is still considered attended
            elif student_attendance_status == "absent":
                absent_sessions_count += 1

            sessions_summary_list.append(StudentAttendanceSessionSummarySchema(
                session_id=session.id,
                session_name=session.session_name,
                start_time=session.start_time,
                end_time=session.end_time,
                day_of_week=session.day_of_week,
                period_range=session.period_range,
                class_id=class_id,
                class_name=class_obj.class_name,
                session_status=session.status, # This is the session's status
                student_attendance_status=student_attendance_status, # This is the student's status
                student_recorded_at=student_recorded_at,
                student_confidence_score=student_confidence_score,
                has_evidence_images=has_evidence_images
            ))
        
        overall_attendance_rate = 0.0
        # Calculate attendance rate based on attended sessions (present + late) vs total sessions
        if total_class_sessions > 0:
            overall_attendance_rate = ((attended_sessions_count) / total_class_sessions) * 100

        return StudentClassAttendanceSummary(
            class_id=class_id,
            class_name=class_obj.class_name,
            total_sessions=total_class_sessions,
            attended_sessions=attended_sessions_count,
            absent_sessions=absent_sessions_count,
            late_sessions=late_sessions_count,
            attendance_rate=round(overall_attendance_rate, 2),
            sessions=sessions_summary_list
        )

    async def get_student_attendance_record_detail(
        self,
        user_id: str,
        record_id: int
    ) -> StudentAttendanceRecordDetailSchema:
        """
        Retrieves detailed attendance record for a specific student, including evidence images.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        # Eager load necessary relationships
        record = self.db.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.session).joinedload(AttendanceSession.class_rel),
            joinedload(AttendanceRecord.images).joinedload(AttendanceImage.file)
        ).filter(
            AttendanceRecord.id == record_id,
            AttendanceRecord.student_id == student_id
        ).first()

        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Attendance record not found or you don't have access."
            )
        
        class_name = record.session.class_rel.name if record.session and record.session.class_rel else "Unknown Class"

        images_data: List[StudentAttendanceImageSchema] = []
        for img_model in record.images:
            file_url = None
            if img_model.file:
                try:
                    file_url = self.file_service.get_file_url(img_model.file.id)
                except Exception as e:
                    print(f"Warning: Could not get URL for file {img_model.file.id}: {e}")
            
            images_data.append(StudentAttendanceImageSchema(
                id=img_model.id,
                file_id=img_model.file.id if img_model.file else None,
                file_url=file_url,
                captured_at=img_model.captured_at
            ))

        return StudentAttendanceRecordDetailSchema(
            id=record.id,
            session_id=record.session_id,
            class_id=record.session.class_id,
            class_name=class_name,
            session_name=record.session.session_name,
            start_time=record.session.start_time,
            end_time=record.session.end_time,
            student_id=record.student_id,
            status=record.status,
            confidence_score=record.confidence_score,
            recorded_at=record.recorded_at,
            notes=record.notes,
            images=images_data
        )

    async def get_student_overall_attendance_report(self, user_id: str) -> StudentAttendanceReportResponse:
        """
        Generates an overall attendance report for a student across all their classes.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        student_obj = self.db.query(Student).options(joinedload(Student.user)).filter(Student.id == student_id).first()
        if not student_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Student not found.")
        
        student_full_name = student_obj.user.full_name if student_obj.user else "Unknown Student"

        class_memberships = self.db.query(ClassMember).filter(ClassMember.student_id == student_id).all()

        classes_summary_list: List[StudentClassAttendanceSummary] = []
        overall_total_sessions = 0
        overall_attended_sessions = 0
        overall_absent_sessions = 0
        overall_late_sessions = 0

        for member in class_memberships:
            # We call the other service method for each class
            class_summary = await self.get_student_class_sessions_attendance(user_id, member.class_id)
            classes_summary_list.append(class_summary)

            overall_total_sessions += class_summary.total_sessions
            overall_attended_sessions += class_summary.attended_sessions
            overall_absent_sessions += class_summary.absent_sessions
            overall_late_sessions += class_summary.late_sessions
        
        overall_attendance_rate = 0.0
        if overall_total_sessions > 0:
            overall_attendance_rate = ((overall_attended_sessions + overall_late_sessions) / overall_total_sessions) * 100

        return StudentAttendanceReportResponse(
            student_id=student_id,
            student_full_name=student_full_name,
            overall_attendance_rate=round(overall_attendance_rate, 2),
            classes_summary=classes_summary_list
        )
