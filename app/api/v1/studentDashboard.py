# app/api/v1/studentDashboard.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.core.dependencies import get_db, get_current_user # Giả sử bạn có hàm get_db trong core/dependencies.py
from app.schemas.studentDashboard import StudentDashboardResponseSchema, DashboardSummarySchema, AttendanceDistributionItemSchema, WeeklyAttendanceItemSchema, MonthlyTrendItemSchema, SubjectAttendanceItemSchema, RecentActivityItemSchema
from app.services.student_dashboard_service import StudentDashboardService
from app.models.user import User as DBUser # Import User model của SQLAlchemy

router = APIRouter()

@router.get(
    "/student/dashboard",
    response_model=StudentDashboardResponseSchema,
    summary="Get student dashboard data",
    description="Retrieve comprehensive dashboard data for the authenticated student, including summary statistics, attendance distribution, weekly and monthly trends, subject-wise attendance, and recent activities.",
    tags=["Student Dashboard"]
)
async def get_student_dashboard(
    current_user: DBUser = Depends(get_current_user), # Lấy thông tin người dùng hiện tại
    db: Session = Depends(get_db)
):
    """
    Endpoint to retrieve all necessary data for the student dashboard.
    The data includes:
    - Summary statistics (total classes, attendance rate, total absences, weekly attendance)
    - Attendance distribution (present, late, absent counts and percentages)
    - Weekly attendance breakdown (present/absent counts per day)
    - Monthly attendance trend over the last 6 months
    - Subject-wise attendance rates
    - Recent activities
    """
    # Đảm bảo người dùng hiện tại là sinh viên
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Only students can view this dashboard."
        )
    
    # Giả sử `current_user.id` là UUID của sinh viên
    # Chuyển đổi UUID sang str nếu service cần str
    student_id_str = str(current_user.id) 

    dashboard_service = StudentDashboardService(db)
    dashboard_data = await dashboard_service.get_student_dashboard_data(student_id_str)
    
    if not dashboard_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dashboard data not found for this student."
        )

    return dashboard_data
