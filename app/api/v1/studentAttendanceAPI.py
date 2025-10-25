# app/api/v1/studentAttendanceAPI.py

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional, List

from app.core.dependencies import get_db, get_current_user
from app.models.user import User as DBUser
from app.schemas.student_attendance import (
    StudentClassAttendanceSummary,
    StudentAttendanceRecordDetailSchema,
    StudentAttendanceReportResponse
)
from app.services.student_attendance_service import StudentAttendanceService

router = APIRouter(prefix="/student-attendance", tags=["Student Attendance"])

@router.get(
    "/class/{class_id}/sessions",
    response_model=StudentClassAttendanceSummary,
    summary="Get student's attendance for a specific class",
    description="Retrieve attendance status for all sessions of a specific class for the authenticated student. Optional filter by session status.",
)
async def get_student_class_attendance_sessions(
    class_id: int,
    session_status_filter: Optional[str] = Query(None, description="Filter sessions by status (e.g., 'scheduled', 'ongoing', 'finished')"),
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to retrieve attendance data for all sessions within a specified class for the authenticated student.
    
    - `class_id`: The ID of the class to retrieve attendance for.
    - `session_status_filter`: Optional. Filter sessions by their status (e.g., 'ongoing', 'finished').
    - Returns a summary of attendance for the class, including details for each session.
    """
    service = StudentAttendanceService(db)
    return await service.get_student_class_sessions_attendance(str(current_user.id), class_id, session_status_filter)

@router.get(
    "/record/{record_id}/detail",
    response_model=StudentAttendanceRecordDetailSchema,
    summary="Get detailed attendance record",
    description="Retrieve detailed information for a specific attendance record, including evidence images, for the authenticated student.",
)
async def get_student_attendance_record_details(
    record_id: int,
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to retrieve detailed information for a specific attendance record.
    This includes the student's status, confidence score, and any associated evidence images.
    
    - `record_id`: The ID of the attendance record to retrieve.
    - Returns a detailed attendance record schema.
    """
    service = StudentAttendanceService(db)
    return await service.get_student_attendance_record_detail(str(current_user.id), record_id)

@router.get(
    "/report/overall",
    response_model=StudentAttendanceReportResponse,
    summary="Get overall student attendance report",
    description="Generates a comprehensive attendance report for the authenticated student across all their enrolled classes.",
)
async def get_student_overall_attendance_report(
    current_user: DBUser = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Endpoint to generate an overall attendance report for the authenticated student.
    This report summarizes attendance across all classes the student is enrolled in,
    including an overall attendance rate and per-class summaries.
    """
    service = StudentAttendanceService(db)
    return await service.get_student_overall_attendance_report(str(current_user.id))
