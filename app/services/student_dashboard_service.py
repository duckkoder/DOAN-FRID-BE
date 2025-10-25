# app/services/student_dashboard_service.py

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import func, extract
from fastapi import HTTPException, status # Thêm import HTTPException, status

from app.models.attendance_record import AttendanceRecord
from app.models.attendance_session import AttendanceSession
from app.models.class_model import Class
from app.models.class_member import ClassMember
from app.models.class_schedule import ClassSchedule
from app.models.leave_request import LeaveRequest
from app.models.user import User # Assuming User model
from app.models.student import Student # Thêm import Student model

from app.schemas.studentDashboard import (
    StudentDashboardResponseSchema,
    DashboardSummarySchema,
    AttendanceDistributionItemSchema,
    WeeklyAttendanceItemSchema,
    MonthlyTrendItemSchema,
    SubjectAttendanceItemSchema,
    RecentActivityItemSchema,
)

class StudentDashboardService:
    def __init__(self, db: Session):
        self.db = db

    def _get_student_id_from_user_id(self, user_id: str) -> int:
        """Helper function to get student_id from user_id."""
        student = self.db.query(Student).filter(Student.user_id == user_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Student profile not found for the given user."
            )
        return student.id

    async def get_dashboard_summary(self, user_id: str) -> DashboardSummarySchema:
        """
        Retrieves summary statistics for the student dashboard.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        # 1. Total classes enrolled
        total_classes = self.db.query(ClassMember).filter(
            ClassMember.student_id == student_id
        ).count()

        # 2. Overall attendance rate and total absences
        # We need to count all attendance records for the student
        # and differentiate between present, late, absent.
        all_records = self.db.query(AttendanceRecord).join(
            AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
        ).join(
            ClassMember, AttendanceSession.class_id == ClassMember.class_id
        ).filter(
            ClassMember.student_id == student_id
        ).filter(
            AttendanceRecord.student_id == student_id
        ).all()

        total_sessions_attended = len(all_records)
        present_count = sum(1 for r in all_records if r.status == "present")
        late_count = sum(1 for r in all_records if r.status == "late")
        absent_count = sum(1 for r in all_records if r.status == "absent")

        attendance_rate = 0.0
        if total_sessions_attended > 0:
            attendance_rate = ((present_count + late_count) / total_sessions_attended) * 100

        # 3. This week's attendance
        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday()) # Monday
        end_of_week = start_of_week + timedelta(days=6) # Sunday

        this_week_sessions = self.db.query(AttendanceSession).join(
            ClassMember, AttendanceSession.class_id == ClassMember.class_id
        ).filter(
            ClassMember.student_id == student_id,
            func.date(AttendanceSession.start_time) >= start_of_week,
            func.date(AttendanceSession.start_time) <= end_of_week
        ).count()

        this_week_attended_records = self.db.query(AttendanceRecord).join(
            AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
        ).join(
            ClassMember, AttendanceSession.class_id == ClassMember.class_id
        ).filter(
            ClassMember.student_id == student_id,
            func.date(AttendanceSession.start_time) >= start_of_week,
            func.date(AttendanceSession.start_time) <= end_of_week,
            AttendanceRecord.status.in_(["present", "late"]) # Attended means present or late
        ).filter(
            AttendanceRecord.student_id == student_id
        ).count()

        return DashboardSummarySchema(
            my_classes=total_classes,
            attendance_rate=round(attendance_rate, 2),
            total_absences=absent_count,
            this_week_attended=this_week_attended_records,
            this_week_total=this_week_sessions,
        )

    async def get_attendance_distribution(self, user_id: str) -> List[AttendanceDistributionItemSchema]:
        """
        Retrieves data for the attendance distribution donut chart.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        # Count present, late, absent for all records
        records_by_status = self.db.query(AttendanceRecord.status, func.count(AttendanceRecord.id)).join(
            AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
        ).join(
            ClassMember, AttendanceSession.class_id == ClassMember.class_id
        ).filter(
            ClassMember.student_id == student_id
        ).filter(
            AttendanceRecord.student_id == student_id
        ).group_by(AttendanceRecord.status).all()

        total_records = sum(count for status, count in records_by_status)

        distribution = []
        for status, count in records_by_status:
            percentage = (count / total_records) * 100 if total_records > 0 else 0
            # Map status to Vietnamese for display based on the image
            display_status = ""
            if status == "present":
                display_status = "Có mặt"
            elif status == "late":
                display_status = "Muộn"
            elif status == "absent":
                display_status = "Vắng"
            else:
                display_status = status # fallback

            distribution.append(AttendanceDistributionItemSchema(
                status=display_status,
                count=count,
                percentage=round(percentage, 2)
            ))
        return distribution

    async def get_weekly_attendance(self, user_id: str) -> List[WeeklyAttendanceItemSchema]:
        """
        Retrieves data for the weekly attendance bar chart.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        today = datetime.now().date()
        start_of_week = today - timedelta(days=today.weekday()) # Monday
        end_of_week = start_of_week + timedelta(days=6) # Sunday

        # Initialize data for all days of the week
        weekly_data_map = {
            "Mon": {"present_count": 0, "absent_count": 0},
            "Tue": {"present_count": 0, "absent_count": 0},
            "Wed": {"present_count": 0, "absent_count": 0},
            "Thu": {"present_count": 0, "absent_count": 0},
            "Fri": {"present_count": 0, "absent_count": 0},
            "Sat": {"present_count": 0, "absent_count": 0},
            "Sun": {"present_count": 0, "absent_count": 0},
        }

        records_this_week = self.db.query(AttendanceRecord.status, AttendanceSession.start_time).join(
            AttendanceSession, AttendanceRecord.session_id == AttendanceSession.id
        ).join(
            ClassMember, AttendanceSession.class_id == ClassMember.class_id
        ).filter(
            ClassMember.student_id == student_id,
            func.date(AttendanceSession.start_time) >= start_of_week,
            func.date(AttendanceSession.start_time) <= end_of_week
        ).filter(
            AttendanceRecord.student_id == student_id
        ).all()

        for status, session_date_time in records_this_week:
            day_of_week = session_date_time.strftime("%a") # e.g., "Mon", "Tue"
            if status in ["present", "late"]:
                weekly_data_map[day_of_week]["present_count"] += 1
            elif status == "absent":
                weekly_data_map[day_of_week]["absent_count"] += 1

        weekly_attendance_list = []
        for day, counts in weekly_data_map.items():
            weekly_attendance_list.append(WeeklyAttendanceItemSchema(
                day=day,
                present_count=counts["present_count"],
                absent_count=counts["absent_count"]
            ))
        
        # Order by day (Mon-Fri as in the image)
        order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        weekly_attendance_list.sort(key=lambda x: order.index(x.day))

        return weekly_attendance_list


    async def get_monthly_trend(self, user_id: str) -> List[MonthlyTrendItemSchema]:
        """
        Retrieves data for the monthly attendance trend line chart (e.g., last 6 months).
        """
        student_id = self._get_student_id_from_user_id(user_id)

        monthly_trends = []
        # Get data for the last 6 months
        for i in range(6, 0, -1): # From 6 months ago to current month
            target_month = datetime.now() - timedelta(days=30 * i) # Approximation
            
            # Get all sessions for the student in the target month
            sessions_in_month = self.db.query(AttendanceSession).join(
                ClassMember, AttendanceSession.class_id == ClassMember.class_id, 
            ).join(
                AttendanceRecord, AttendanceSession.id == AttendanceRecord.session_id
            ).filter(
                ClassMember.student_id == student_id,
                extract('month', AttendanceSession.start_time) == target_month.month,
                extract('year', AttendanceSession.start_time) == target_month.year,
                AttendanceRecord.student_id == student_id
            ).all()

            total_sessions_in_month = len(sessions_in_month)
            
            if total_sessions_in_month > 0:
                # Get attendance records for these sessions
                session_ids_in_month = [s.id for s in sessions_in_month]
                attended_records_in_month = self.db.query(AttendanceRecord).filter(
                    AttendanceRecord.student_id == student_id,
                    AttendanceRecord.session_id.in_(session_ids_in_month),
                    AttendanceRecord.status.in_(["present", "late"])
                ).count()
                
                monthly_rate = (attended_records_in_month / total_sessions_in_month) * 100
            else:
                monthly_rate = 0.0

            monthly_trends.append(MonthlyTrendItemSchema(
                month=target_month.strftime("%b"), # e.g., "Jan", "Feb"
                attendance_rate=round(monthly_rate, 2)
            ))
        return monthly_trends


    async def get_subject_wise_attendance(self, user_id: str) -> List[SubjectAttendanceItemSchema]:
        """
        Retrieves data for subject-wise attendance progress bars.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        subject_attendance_list = []
        student_classes = self.db.query(ClassMember).filter(ClassMember.student_id == student_id).all()

        for class_member in student_classes:
            class_info = self.db.query(Class).filter(Class.id == class_member.class_id).first()
            if class_info:
                # Get all sessions for this class
                all_sessions_for_class = self.db.query(AttendanceSession).filter(
                    AttendanceSession.class_id == class_info.id
                ).all()
                total_sessions_for_subject = len(all_sessions_for_class)
                
                if total_sessions_for_subject > 0:
                    # Get attended records for this student in this class
                    session_ids_for_class = [s.id for s in all_sessions_for_class]
                    attended_records_for_subject = self.db.query(AttendanceRecord).filter(
                        AttendanceRecord.student_id == student_id,
                        AttendanceRecord.session_id.in_(session_ids_for_class),
                        AttendanceRecord.status.in_(["present", "late"])
                    ).count()
                    
                    subject_rate = (attended_records_for_subject / total_sessions_for_subject) * 100
                else:
                    subject_rate = 0.0

                subject_attendance_list.append(SubjectAttendanceItemSchema(
                    subject_name=class_info.class_name, # Assuming class_info.name is the subject name
                    attendance_rate=round(subject_rate, 2),
                    total_sessions=total_sessions_for_subject
                ))
        return subject_attendance_list

    async def get_recent_activity(self, user_id: str, limit: int = 3) -> List[RecentActivityItemSchema]:
        """
        Retrieves a list of recent activities for the student.
        This could include new attendance records, leave request submissions, etc.
        """
        student_id = self._get_student_id_from_user_id(user_id)

        activities = []

        # Recent attendance records
        # Need to eager load session and class_rel to access class name
        from sqlalchemy.orm import joinedload
        recent_attendance = self.db.query(AttendanceRecord).options(
            joinedload(AttendanceRecord.session).joinedload(AttendanceSession.class_rel)
        ).filter(
            AttendanceRecord.student_id == student_id,
            AttendanceRecord.status.in_(["present", "late"])
        ).order_by(AttendanceRecord.recorded_at.desc()).limit(limit).all()

        for record in recent_attendance:
            class_name = record.session.class_rel.name if record.session and record.session.class_rel else "Unknown Class"
            description = f"Attended {class_name} class"
            activities.append(RecentActivityItemSchema(
                description=description,
                timestamp=record.recorded_at
            ))

        # Recent leave requests
        # Corrected: Load LeaveRequest.class_rel directly, as LeaveRequest has a direct relationship to Class.
        recent_leave_requests = self.db.query(LeaveRequest).options(
            joinedload(LeaveRequest.class_rel) # Sửa lỗi ở đây: chỉ cần load class_rel trực tiếp
        ).filter(
            LeaveRequest.student_id == student_id
        ).order_by(LeaveRequest.created_at.desc()).limit(limit).all()

        for lr in recent_leave_requests:
            # Corrected: Access class name directly from lr.class_rel
            class_name = lr.class_rel.class_name if lr.class_rel else "Unknown Class" # Sửa lỗi ở đây
            description = f"Appeal submitted for {class_name} class"
            activities.append(RecentActivityItemSchema(
                description=description,
                timestamp=lr.created_at
            ))
        
        # Combine and sort activities by timestamp
        activities.sort(key=lambda x: x.timestamp, reverse=True)
        return activities[:limit] # Return only the top 'limit' activities


    async def get_student_dashboard_data(self, user_id: str) -> StudentDashboardResponseSchema:
        """
        Aggregates all dashboard data for a student.
        """
        summary = await self.get_dashboard_summary(user_id)
        attendance_distribution = await self.get_attendance_distribution(user_id)
        weekly_attendance = await self.get_weekly_attendance(user_id)
        monthly_trend = await self.get_monthly_trend(user_id)
        subject_wise_attendance = await self.get_subject_wise_attendance(user_id)
        recent_activity = await self.get_recent_activity(user_id)

        return StudentDashboardResponseSchema(
            summary=summary,
            attendance_distribution=attendance_distribution,
            weekly_attendance=weekly_attendance,
            monthly_trend=monthly_trend,
            subject_wise_attendance=subject_wise_attendance,
            recent_activity=recent_activity,
        )
