"""Service for leave request operations."""
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.leave_request import LeaveRequest
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.class_model import Class
from app.models.class_member import ClassMember
from app.models.user import User
from app.models.file import File
from app.schemas.leaveRequest import (
    CreateLeaveRequestRequest,
    UpdateLeaveRequestRequest,
    ReviewLeaveRequestRequest
)
from app.services.file_service import FileService


class LeaveRequestService:
    
    @staticmethod
    async def create_leave_request(
        db: Session,
        user,
        payload: CreateLeaveRequestRequest
    ) -> Dict:
        """
        Create a new leave request (Student only).
        
        Validation:
        - User must be a student
        - Student must be enrolled in the class
        - Class must be active
        """
        
        # Verify student exists
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can create leave requests"
            )
        
        # Verify class exists and is active
        cls = db.query(Class).filter(Class.id == payload.class_id).first()
        if not cls:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Class not found"
            )
        
        if not cls.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create leave request for inactive class"
            )
        
        # Verify student is enrolled in this class
        member = db.query(ClassMember).filter(
            ClassMember.student_id == student.id,
            ClassMember.class_id == payload.class_id
        ).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not enrolled in this class"
            )
        
        # Verify class schedule matches the leave request
        from app.models.class_schedule import ClassSchedule
        class_schedule = db.query(ClassSchedule).filter(
            ClassSchedule.class_id == payload.class_id
        ).first()
        
        if not class_schedule or not class_schedule.schedule_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Class schedule not found. Cannot create leave request."
            )
        
        # Validate day_of_week and time_slot against schedule
        # Note: schedule_data uses lowercase keys (monday, tuesday, etc.)
        # but API accepts capitalized format (Monday, Tuesday, etc.)
        schedule_data = class_schedule.schedule_data
        day_key = payload.day_of_week.lower()  # Convert "Monday" -> "monday" for DB lookup
        
        if day_key not in schedule_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Class does not have schedule on {payload.day_of_week}"
            )
        
        # Parse time_slot to get start and end periods
        time_parts = payload.time_slot.split('-')
        request_start = int(time_parts[0])
        request_end = int(time_parts[1])
        request_periods = set(range(request_start, request_end + 1))
        
        # Get class periods from schedule (e.g., ["1-3", "6-9"])
        class_periods = schedule_data[day_key]
        if not class_periods:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Class does not have any periods scheduled on {payload.day_of_week}"
            )
        
        # Convert class periods to set of individual periods
        all_class_periods = set()
        for period_range in class_periods:
            if isinstance(period_range, str) and '-' in period_range:
                parts = period_range.split('-')
                start = int(parts[0])
                end = int(parts[1])
                all_class_periods.update(range(start, end + 1))
            elif isinstance(period_range, int):
                all_class_periods.add(period_range)
        
        # Check if requested periods are within class schedule
        if not request_periods.issubset(all_class_periods):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Time slot {payload.time_slot} does not match class schedule on {payload.day_of_week}. Class periods: {class_periods}"
            )
        
        # Verify evidence file if provided
        if payload.evidence_file_id:
            evidence = db.query(File).filter(File.id == payload.evidence_file_id).first()
            if not evidence:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Evidence file not found"
                )
        
        # Create leave request
        leave_request = LeaveRequest(
            student_id=student.id,
            class_id=payload.class_id,
            reason=payload.reason,
            leave_date=payload.leave_date,
            day_of_week=payload.day_of_week,
            time_slot=payload.time_slot,
            evidence_file_id=payload.evidence_file_id,
            status="pending"
        )
        
        db.add(leave_request)
        db.commit()
        db.refresh(leave_request)
        
        # Get student and class info for response
        student_user = db.query(User).filter(User.id == user.id).first()
        
        return {
            "success": True,
            "data": {
                "leaveRequest": {
                    "id": leave_request.id,
                    "studentId": student.id,
                    "studentName": student_user.full_name,
                    "classId": cls.id,
                    "className": cls.class_name,
                    "reason": leave_request.reason,
                    "leaveDate": leave_request.leave_date.isoformat() + "Z",
                    "dayOfWeek": leave_request.day_of_week,
                    "timeSlot": leave_request.time_slot,
                    "status": leave_request.status,
                    "createdAt": leave_request.created_at.isoformat() + "Z"
                }
            },
            "message": "Leave request created successfully"
        }
    
    @staticmethod
    async def get_leave_requests(
        db: Session,
        user,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None
    ) -> Dict:
        """
        Get leave requests.
        
        - Student: Get own leave requests (all statuses)
        - Teacher: Get leave requests for their classes (exclude cancelled)
        """
        
        # Check if user is student or teacher
        student = db.query(Student).filter(Student.user_id == user.id).first()
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        
        if student:
            # Student: Get own requests (all statuses including cancelled)
            query = db.query(LeaveRequest).filter(LeaveRequest.student_id == student.id)
            
            if class_id:
                query = query.filter(LeaveRequest.class_id == class_id)
            
            if status_filter:
                query = query.filter(LeaveRequest.status == status_filter)
            
            requests = query.order_by(LeaveRequest.created_at.desc()).all()
            
        elif teacher:
            # Teacher: Get requests for their classes (exclude cancelled)
            query = db.query(LeaveRequest).join(
                Class, LeaveRequest.class_id == Class.id
            ).filter(
                Class.teacher_id == teacher.id,
                LeaveRequest.status != "cancelled"  # ✅ Exclude cancelled requests
            )
            
            if class_id:
                query = query.filter(LeaveRequest.class_id == class_id)
            
            if status_filter:
                query = query.filter(LeaveRequest.status == status_filter)
            
            requests = query.order_by(LeaveRequest.created_at.desc()).all()
            
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Initialize FileService
        file_service = FileService(db)
        
        # Build response
        requests_data = []
        for req in requests:
            # Get student info
            student_obj = db.query(Student).filter(Student.id == req.student_id).first()
            student_user = db.query(User).filter(User.id == student_obj.user_id).first() if student_obj else None
            
            # Get class info
            cls = db.query(Class).filter(Class.id == req.class_id).first()
            
            # ✅ Get evidence file URL using FileService
            evidence_url = None
            if req.evidence_file_id:
                try:
                    evidence_url = file_service.get_file_url(req.evidence_file_id)
                except Exception as e:
                    print(f"Warning: Failed to get evidence URL for file {req.evidence_file_id}: {str(e)}")
            
            # Get reviewer info if reviewed
            reviewer_name = None
            if req.reviewed_by:
                reviewer = db.query(Teacher).filter(Teacher.id == req.reviewed_by).first()
                if reviewer:
                    reviewer_user = db.query(User).filter(User.id == reviewer.user_id).first()
                    reviewer_name = reviewer_user.full_name if reviewer_user else None
            
            requests_data.append({
                "id": req.id,
                "studentId": req.student_id,
                "studentName": student_user.full_name if student_user else "Unknown",
                "classId": req.class_id,
                "className": cls.class_name if cls else "Unknown",
                "reason": req.reason,
                "leaveDate": req.leave_date.isoformat() + "Z",
                "dayOfWeek": req.day_of_week,
                "timeSlot": req.time_slot,
                "evidenceFileId": req.evidence_file_id,
                "evidenceFileUrl": evidence_url,
                "status": req.status,
                "reviewedBy": req.reviewed_by,
                "reviewerName": reviewer_name,
                "reviewNotes": req.review_notes,
                "reviewedAt": req.reviewed_at.isoformat() + "Z" if req.reviewed_at else None,
                "createdAt": req.created_at.isoformat() + "Z",
                "updatedAt": req.updated_at.isoformat() + "Z" if req.updated_at else None
            })
        
        return {
            "success": True,
            "data": {
                "leaveRequests": requests_data,
                "total": len(requests_data)
            }
        }
    
    @staticmethod
    async def get_leave_request_detail(
        db: Session,
        user,
        request_id: int
    ) -> Dict:
        """Get leave request detail."""
        
        leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Check permission
        student = db.query(Student).filter(Student.user_id == user.id).first()
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        
        if student:
            # Student can only view own requests
            if leave_request.student_id != student.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        elif teacher:
            # Teacher can view requests for their classes
            cls = db.query(Class).filter(Class.id == leave_request.class_id).first()
            if not cls or cls.teacher_id != teacher.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied"
            )
        
        # Get related info
        student_obj = db.query(Student).filter(Student.id == leave_request.student_id).first()
        student_user = db.query(User).filter(User.id == student_obj.user_id).first() if student_obj else None
        
        cls = db.query(Class).filter(Class.id == leave_request.class_id).first()
        
        # ✅ Get evidence file URL using FileService
        evidence_url = None
        if leave_request.evidence_file_id:
            try:
                file_service = FileService(db)
                evidence_url = file_service.get_file_url(leave_request.evidence_file_id)
            except Exception as e:
                print(f"Warning: Failed to get evidence URL for file {leave_request.evidence_file_id}: {str(e)}")
        
        reviewer_name = None
        if leave_request.reviewed_by:
            reviewer = db.query(Teacher).filter(Teacher.id == leave_request.reviewed_by).first()
            if reviewer:
                reviewer_user = db.query(User).filter(User.id == reviewer.user_id).first()
                reviewer_name = reviewer_user.full_name if reviewer_user else None
        
        return {
            "success": True,
            "data": {
                "leaveRequest": {
                    "id": leave_request.id,
                    "studentId": leave_request.student_id,
                    "studentName": student_user.full_name if student_user else "Unknown",
                    "classId": leave_request.class_id,
                    "className": cls.class_name if cls else "Unknown",
                    "reason": leave_request.reason,
                    "leaveDate": leave_request.leave_date.isoformat() + "Z",
                    "dayOfWeek": leave_request.day_of_week,
                    "timeSlot": leave_request.time_slot,
                    "evidenceFileId": leave_request.evidence_file_id,
                    "evidenceFileUrl": evidence_url,  # ✅ Added file URL
                    "status": leave_request.status,
                    "reviewedBy": leave_request.reviewed_by,
                    "reviewerName": reviewer_name,
                    "reviewNotes": leave_request.review_notes,
                    "reviewedAt": leave_request.reviewed_at.isoformat() + "Z" if leave_request.reviewed_at else None,
                    "createdAt": leave_request.created_at.isoformat() + "Z",
                    "updatedAt": leave_request.updated_at.isoformat() + "Z" if leave_request.updated_at else None
                }
            }
        }
    
    @staticmethod
    async def update_leave_request(
        db: Session,
        user,
        request_id: int,
        payload: UpdateLeaveRequestRequest
    ) -> Dict:
        """
        Update leave request (Student only, only pending status).
        """
        
        # Verify student
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can update leave requests"
            )
        
        # Get leave request
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id,
            LeaveRequest.student_id == student.id
        ).first()
        
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Check status
        if leave_request.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot update leave request with status '{leave_request.status}'"
            )
        
        # If updating day_of_week or time_slot, validate against class schedule
        if payload.day_of_week is not None or payload.time_slot is not None:
            from app.models.class_schedule import ClassSchedule
            
            # Get current values or use new values
            new_day = payload.day_of_week if payload.day_of_week is not None else leave_request.day_of_week
            new_time_slot = payload.time_slot if payload.time_slot is not None else leave_request.time_slot
            
            # Get class schedule
            class_schedule = db.query(ClassSchedule).filter(
                ClassSchedule.class_id == leave_request.class_id
            ).first()
            
            if not class_schedule or not class_schedule.schedule_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Class schedule not found. Cannot update leave request."
                )
            
            # Validate against schedule
            # Note: schedule_data uses lowercase keys but API accepts capitalized format
            schedule_data = class_schedule.schedule_data
            day_key = new_day.lower()  # Convert "Monday" -> "monday" for DB lookup
            
            if day_key not in schedule_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Class does not have schedule on {new_day}"
                )
            
            # Parse time_slot
            time_parts = new_time_slot.split('-')
            request_start = int(time_parts[0])
            request_end = int(time_parts[1])
            request_periods = set(range(request_start, request_end + 1))
            
            # Get class periods
            class_periods = schedule_data[day_key]
            if not class_periods:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Class does not have any periods scheduled on {new_day}"
                )
            
            # Convert class periods to set
            all_class_periods = set()
            for period_range in class_periods:
                if isinstance(period_range, str) and '-' in period_range:
                    parts = period_range.split('-')
                    start = int(parts[0])
                    end = int(parts[1])
                    all_class_periods.update(range(start, end + 1))
                elif isinstance(period_range, int):
                    all_class_periods.add(period_range)
            
            # Check if requested periods match
            if not request_periods.issubset(all_class_periods):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Time slot {new_time_slot} does not match class schedule on {new_day}. Class periods: {class_periods}"
                )
        
        # Update fields
        if payload.reason is not None:
            leave_request.reason = payload.reason
        if payload.leave_date is not None:
            leave_request.leave_date = payload.leave_date
        if payload.day_of_week is not None:
            leave_request.day_of_week = payload.day_of_week
        if payload.time_slot is not None:
            leave_request.time_slot = payload.time_slot
        
        # ✅ Handle evidence file update
        if payload.evidence_file_id is not None:
            # Store old evidence_file_id for deletion
            old_evidence_id = leave_request.evidence_file_id
            
            # Verify new file exists if provided
            if payload.evidence_file_id > 0:
                new_evidence = db.query(File).filter(File.id == payload.evidence_file_id).first()
                if not new_evidence:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Evidence file not found"
                    )
                
                # Check if new file belongs to the student
                if new_evidence.uploader_id != user.id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="You can only use your own uploaded files"
                    )
            
            # Update to new evidence_file_id
            leave_request.evidence_file_id = payload.evidence_file_id if payload.evidence_file_id > 0 else None
            
            # ✅ Delete old evidence file if exists and is different from new one
            if old_evidence_id and old_evidence_id != payload.evidence_file_id:
                try:
                    file_service = FileService(db)
                    file_service.delete_file(old_evidence_id, user.id)
                except Exception as e:
                    # Log error but don't fail the update
                    print(f"Warning: Failed to delete old evidence file {old_evidence_id}: {str(e)}")
        
        leave_request.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(leave_request)
        
        return {
            "success": True,
            "data": {
                "leaveRequest": {
                    "id": leave_request.id,
                    "updatedAt": leave_request.updated_at.isoformat() + "Z"
                }
            },
            "message": "Leave request updated successfully"
        }
    
    @staticmethod
    async def review_leave_request(
        db: Session,
        user,
        request_id: int,
        payload: ReviewLeaveRequestRequest
    ) -> Dict:
        """
        Review (approve/reject) leave request (Teacher only).
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can review leave requests"
            )
        
        # Get leave request
        leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == request_id).first()
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Verify teacher owns this class
        cls = db.query(Class).filter(Class.id == leave_request.class_id).first()
        if not cls or cls.teacher_id != teacher.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only review leave requests for your classes"
            )
        
        # Check if already reviewed
        if leave_request.status in ["approved", "rejected", "cancelled"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Leave request already {leave_request.status}"
            )
        
        # Update status
        leave_request.status = payload.status
        leave_request.reviewed_by = teacher.id
        leave_request.review_notes = payload.review_notes
        leave_request.reviewed_at = datetime.utcnow()
        leave_request.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(leave_request)
        
        return {
            "success": True,
            "data": {
                "leaveRequest": {
                    "id": leave_request.id,
                    "status": leave_request.status,
                    "reviewedAt": leave_request.reviewed_at.isoformat() + "Z"
                }
            },
            "message": f"Leave request {payload.status} successfully"
        }
    
    @staticmethod
    async def cancel_leave_request(
        db: Session,
        user,
        request_id: int
    ) -> Dict:
        """
        Cancel leave request (Student only, only pending status).
        
        ✅ Also deletes associated evidence file.
        """
        
        # Verify student
        student = db.query(Student).filter(Student.user_id == user.id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only students can cancel leave requests"
            )
        
        # Get leave request
        leave_request = db.query(LeaveRequest).filter(
            LeaveRequest.id == request_id,
            LeaveRequest.student_id == student.id
        ).first()
        
        if not leave_request:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Leave request not found"
            )
        
        # Check status
        if leave_request.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel leave request with status '{leave_request.status}'"
            )
        
        # ✅ Delete evidence file if exists
        if leave_request.evidence_file_id:
            try:
                file_service = FileService(db)
                file_service.delete_file(leave_request.evidence_file_id, user.id)
            except Exception as e:
                # Log error but don't fail the cancellation
                print(f"Warning: Failed to delete evidence file {leave_request.evidence_file_id}: {str(e)}")
        
        # Update status to cancelled
        leave_request.status = "cancelled"
        leave_request.updated_at = datetime.utcnow()
        
        db.commit()
        
        return {
            "success": True,
            "message": "Leave request cancelled successfully"
        }
    
    @staticmethod
    async def get_teacher_leave_requests_with_stats(
        db: Session,
        user,
        class_id: Optional[int] = None,
        status_filter: Optional[str] = None
    ) -> Dict:
        """
        Get leave requests for teacher with enhanced statistics.
        
        Returns:
        - Leave requests list (exclude cancelled)
        - Overall summary statistics (exclude cancelled from counts)
        - Per-class summary statistics (exclude cancelled)
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can access this endpoint"
            )
        
        # Base query for teacher's classes (exclude cancelled)
        query = db.query(LeaveRequest).join(
            Class, LeaveRequest.class_id == Class.id
        ).filter(
            Class.teacher_id == teacher.id,
            LeaveRequest.status != "cancelled"  # ✅ Exclude cancelled requests
        )
        
        # Apply filters
        if class_id:
            query = query.filter(LeaveRequest.class_id == class_id)

        if status_filter != "all":
            query = query.filter(LeaveRequest.status == status_filter)
        
        requests = query.order_by(LeaveRequest.created_at.desc()).all()
        
        # Calculate overall summary (exclude cancelled)
        all_requests = db.query(LeaveRequest).join(
            Class, LeaveRequest.class_id == Class.id
        ).filter(
            Class.teacher_id == teacher.id,
            LeaveRequest.status != "cancelled"  # ✅ Exclude cancelled from stats
        ).all()
        
        summary = {
            "totalRequests": len(all_requests),
            "pendingCount": sum(1 for r in all_requests if r.status == "pending"),
            "approvedCount": sum(1 for r in all_requests if r.status == "approved"),
            "rejectedCount": sum(1 for r in all_requests if r.status == "rejected")
        }
        
        # Calculate per-class summary (exclude cancelled)
        classes = db.query(Class).filter(Class.teacher_id == teacher.id).all()
        class_summary = []
        
        for cls in classes:
            class_requests = [r for r in all_requests if r.class_id == cls.id]  # all_requests already excludes cancelled
            class_summary.append({
                "classId": cls.id,
                "className": cls.class_name,
                "totalRequests": len(class_requests),
                "pendingCount": sum(1 for r in class_requests if r.status == "pending"),
                "approvedCount": sum(1 for r in class_requests if r.status == "approved"),
                "rejectedCount": sum(1 for r in class_requests if r.status == "rejected")
            })
        
        # ✅ Initialize FileService
        file_service = FileService(db)
        
        # Build detailed requests data
        requests_data = []
        for req in requests:
            # Get student info
            student_obj = db.query(Student).filter(Student.id == req.student_id).first()
            student_user = db.query(User).filter(User.id == student_obj.user_id).first() if student_obj else None
            
            # Get class info
            cls = db.query(Class).filter(Class.id == req.class_id).first()
            
            # ✅ Get evidence file URL using FileService
            evidence_url = None
            if req.evidence_file_id:
                try:
                    evidence_url = file_service.get_file_url(req.evidence_file_id)
                except Exception as e:
                    print(f"Warning: Failed to get evidence URL for file {req.evidence_file_id}: {str(e)}")
            
            # Get reviewer info
            reviewer_name = None
            if req.reviewed_by:
                reviewer = db.query(Teacher).filter(Teacher.id == req.reviewed_by).first()
                if reviewer:
                    reviewer_user = db.query(User).filter(User.id == reviewer.user_id).first()
                    reviewer_name = reviewer_user.full_name if reviewer_user else None
            
            requests_data.append({
                "id": req.id,
                "studentId": req.student_id,
                "studentName": student_user.full_name if student_user else "Unknown",
                "studentCode": student_obj.student_code if student_obj else None,
                "classId": req.class_id,
                "className": cls.class_name if cls else "Unknown",
                "reason": req.reason,
                "leaveDate": req.leave_date.isoformat() + "Z",
                "dayOfWeek": req.day_of_week,
                "timeSlot": req.time_slot,
                "evidenceFileId": req.evidence_file_id,
                "evidenceFileUrl": evidence_url,
                "status": req.status,
                "reviewedBy": req.reviewed_by,
                "reviewerName": reviewer_name,
                "reviewNotes": req.review_notes,
                "reviewedAt": req.reviewed_at.isoformat() + "Z" if req.reviewed_at else None,
                "createdAt": req.created_at.isoformat() + "Z",
                "updatedAt": req.updated_at.isoformat() + "Z" if req.updated_at else None
            })
        
        return {
            "success": True,
            "data": {
                "leaveRequests": requests_data,
                "total": len(requests_data),
                "summary": summary,
                "classSummary": class_summary
            }
        }
    
    @staticmethod
    async def batch_review_leave_requests(
        db: Session,
        user,
        request_ids: List[int],
        status: str,
        review_notes: Optional[str] = None
    ) -> Dict:
        """
        Batch review multiple leave requests at once.
        """
        
        # Verify teacher
        teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
        if not teacher:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only teachers can review leave requests"
            )
        
        results = []
        success_count = 0
        failed_count = 0
        
        for req_id in request_ids:
            try:
                # Get leave request
                leave_request = db.query(LeaveRequest).filter(LeaveRequest.id == req_id).first()
                
                if not leave_request:
                    results.append({
                        "id": req_id,
                        "success": False,
                        "error": "Leave request not found"
                    })
                    failed_count += 1
                    continue
                
                # Verify teacher owns this class
                cls = db.query(Class).filter(Class.id == leave_request.class_id).first()
                if not cls or cls.teacher_id != teacher.id:
                    results.append({
                        "id": req_id,
                        "success": False,
                        "error": "Access denied"
                    })
                    failed_count += 1
                    continue
                
                # Check if already reviewed
                if leave_request.status in ["approved", "rejected", "cancelled"]:
                    results.append({
                        "id": req_id,
                        "success": False,
                        "error": f"Already {leave_request.status}"
                    })
                    failed_count += 1
                    continue
                
                # Update status
                leave_request.status = status
                leave_request.reviewed_by = teacher.id
                leave_request.review_notes = review_notes
                leave_request.reviewed_at = datetime.utcnow()
                leave_request.updated_at = datetime.utcnow()
                
                results.append({
                    "id": req_id,
                    "status": status,
                    "success": True
                })
                success_count += 1
                
            except Exception as e:
                results.append({
                    "id": req_id,
                    "success": False,
                    "error": str(e)
                })
                failed_count += 1
        
        db.commit()
        
        return {
            "success": True,
            "data": {
                "successCount": success_count,
                "failedCount": failed_count,
                "results": results
            },
            "message": f"Batch review completed: {success_count} {status}, {failed_count} failed"
        }