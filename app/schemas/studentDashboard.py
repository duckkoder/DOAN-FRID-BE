# app/schemas/dashboard.py

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

# 1. Dashboard Summary
class DashboardSummarySchema(BaseModel):
    my_classes: int = Field(..., description="Total number of classes the student is enrolled in.")
    attendance_rate: float = Field(..., description="Overall attendance rate in percentage.")
    total_absences: int = Field(..., description="Total number of absences across all classes.")
    this_week_attended: int = Field(..., description="Number of classes attended this week.")
    this_week_total: int = Field(..., description="Total number of classes scheduled this week.")

# 2. Attendance Distribution (Donut Chart)
class AttendanceDistributionItemSchema(BaseModel):
    status: str = Field(..., description="Attendance status (e.g., 'Có mặt', 'Muộn', 'Vắng').")
    count: int = Field(..., description="Number of sessions for this status.")
    percentage: float = Field(..., description="Percentage of sessions for this status.")

# 3. Weekly Attendance (Bar Chart)
class WeeklyAttendanceItemSchema(BaseModel):
    day: str = Field(..., description="Day of the week (e.g., 'Mon', 'Tue').")
    present_count: int = Field(..., description="Number of present sessions for the day.")
    absent_count: int = Field(..., description="Number of absent sessions for the day.")

# 4. Monthly Trend (Line Chart)
class MonthlyTrendItemSchema(BaseModel):
    month: str = Field(..., description="Month (e.g., 'Jan', 'Feb').")
    attendance_rate: float = Field(..., description="Attendance rate in percentage for the month.")

# 5. Subject-wise Attendance (Progress Bars)
class SubjectAttendanceItemSchema(BaseModel):
    subject_name: str = Field(..., description="Name of the subject/class.")
    attendance_rate: float = Field(..., description="Attendance rate in percentage for this subject.")
    total_sessions: int = Field(..., description="Total sessions for this subject.")

# 6. Recent Activity
class RecentActivityItemSchema(BaseModel):
    description: str = Field(..., description="Description of the activity.")
    timestamp: datetime = Field(..., description="Timestamp when the activity occurred.")

# Main Dashboard Response Schema
class StudentDashboardResponseSchema(BaseModel):
    summary: DashboardSummarySchema = Field(..., description="Summary statistics for the dashboard.")
    attendance_distribution: List[AttendanceDistributionItemSchema] = Field(..., description="Data for the attendance distribution donut chart.")
    weekly_attendance: List[WeeklyAttendanceItemSchema] = Field(..., description="Data for the weekly attendance bar chart.")
    monthly_trend: List[MonthlyTrendItemSchema] = Field(..., description="Data for the monthly attendance trend line chart.")
    subject_wise_attendance: List[SubjectAttendanceItemSchema] = Field(..., description="Data for subject-wise attendance progress bars.")
    recent_activity: List[RecentActivityItemSchema] = Field(..., description="List of recent activities.")
