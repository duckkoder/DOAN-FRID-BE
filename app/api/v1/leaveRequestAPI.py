"""Leave request endpoints."""
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.leaveRequest import (
    CreateLeaveRequestRequest,
    CreateLeaveRequestResponse,
    UpdateLeaveRequestRequest,
    UpdateLeaveRequestResponse,
    ReviewLeaveRequestRequest,
    ReviewLeaveRequestResponse,
    GetLeaveRequestsResponse,
    GetLeaveRequestDetailResponse,
    CancelLeaveRequestResponse,
    GetTeacherLeaveRequestsResponse,
    BatchReviewRequest,
    BatchReviewResponse
)
from app.services.leaveRequest_service import LeaveRequestService

router = APIRouter(prefix="/leave-requests", tags=["Leave Requests"])


@router.post("", response_model=CreateLeaveRequestResponse, status_code=status.HTTP_201_CREATED)
async def create_leave_request(
    payload: CreateLeaveRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new leave request (Student only).
    
    - Requires: Student role, enrolled in the class
    - Body: class_id, reason, leave_date, day_of_week, time_slot, evidence_file_id
    - Returns: Created leave request info
    """
    result = await LeaveRequestService.create_leave_request(db, current_user, payload)
    return result


@router.get("", response_model=GetLeaveRequestsResponse)
async def get_leave_requests(
    class_id: int = Query(None, description="Filter by class ID"),
    status: str = Query(None, description="Filter: pending|approved|rejected|cancelled"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get leave requests.
    
    - Student: Get own leave requests
    - Teacher: Get leave requests for their classes
    - Query params: class_id, status (optional)
    """
    result = await LeaveRequestService.get_leave_requests(db, current_user, class_id, status)
    return result


@router.get("/{request_id}", response_model=GetLeaveRequestDetailResponse)
async def get_leave_request_detail(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get leave request detail.
    
    - Student: Can view own requests
    - Teacher: Can view requests for their classes
    """
    result = await LeaveRequestService.get_leave_request_detail(db, current_user, request_id)
    return result


@router.put("/{request_id}", response_model=UpdateLeaveRequestResponse)
async def update_leave_request(
    request_id: int,
    payload: UpdateLeaveRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update leave request (Student only, only pending status).
    
    - Path param: request_id
    - Body: reason, leave_date, day_of_week, time_slot, evidence_file_id (all optional)
    - Returns: Updated leave request info
    """
    result = await LeaveRequestService.update_leave_request(db, current_user, request_id, payload)
    return result


@router.post("/{request_id}/review", response_model=ReviewLeaveRequestResponse)
async def review_leave_request(
    request_id: int,
    payload: ReviewLeaveRequestRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Review (approve/reject) leave request (Teacher only).
    
    - Path param: request_id
    - Body: status (approved|rejected), review_notes
    - Returns: Reviewed leave request info
    """
    result = await LeaveRequestService.review_leave_request(db, current_user, request_id, payload)
    return result


@router.delete("/{request_id}", response_model=CancelLeaveRequestResponse)
async def cancel_leave_request(
    request_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Cancel leave request (Student only, only pending status).
    
    - Path param: request_id
    - Returns: Success message
    """
    result = await LeaveRequestService.cancel_leave_request(db, current_user, request_id)
    return result


@router.get("/teacher/statistics", response_model=GetTeacherLeaveRequestsResponse)
async def get_teacher_leave_requests_with_stats(
    class_id: int = Query(None, description="Filter by class ID"),
    status: str = Query(None, description="Filter: pending|approved|rejected|cancelled"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get leave requests for teacher with statistics (Teacher only).
    
    - Returns: Enhanced response with summary stats and per-class breakdown
    - Query params: class_id, status (optional)
    """
    result = await LeaveRequestService.get_teacher_leave_requests_with_stats(
        db, current_user, class_id, status
    )
    return result


@router.post("/batch-review", response_model=BatchReviewResponse)
async def batch_review_leave_requests(
    payload: BatchReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Batch review multiple leave requests at once (Teacher only).
    
    - Body: request_ids (list), status (approved|rejected), review_notes
    - Returns: Success/failure count and detailed results
    """
    result = await LeaveRequestService.batch_review_leave_requests(
        db, current_user, payload.request_ids, payload.status, payload.review_notes
    )
    return result