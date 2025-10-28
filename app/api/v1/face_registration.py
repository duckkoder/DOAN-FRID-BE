"""REST API endpoints for face registration (non-WebSocket)."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database.session import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.face_registration_service import FaceRegistrationDBService

router = APIRouter(prefix="/face-registration", tags=["Face Registration"])


@router.get(
    "/status/{student_id}",
    summary="Get face registration status for a student",
    description="Check if student has any face registration request and its current status."
)
async def get_registration_status(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get face registration status for a specific student.
    
    Returns:
    - status: Current status (null, collecting, pending_student_review, pending_admin_review, approved, rejected, cancelled)
    - registration_id: ID of the registration request (if exists)
    - message: Human-readable message
    - can_register: Whether student can start/continue registration
    - details: Additional information
    """
    # Only allow student to check their own status, or admin to check any
    if current_user.role == "student":
        # For students, check if they're checking their own status
        if not current_user.student or current_user.student.id != student_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You can only check your own registration status"
            )
    elif current_user.role != "admin":
        # For other roles (teacher, etc.), deny access
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students and admins can check registration status"
        )
    
    service = FaceRegistrationDBService(db)
    
    # Get most recent registration request
    from app.models.face_registration_request import FaceRegistrationRequest
    registration = (
        db.query(FaceRegistrationRequest)
        .filter(FaceRegistrationRequest.student_id == student_id)
        .order_by(FaceRegistrationRequest.created_at.desc())
        .first()
    )
    
    if not registration:
        return {
            "status": None,
            "registration_id": None,
            "message": "Chưa có yêu cầu đăng ký khuôn mặt",
            "can_register": True,
            "details": None
        }
    
    # Determine if student can register based on status
    can_register = registration.status in ["rejected", "cancelled", "collecting"]
    
    # Build response based on status
    status_messages = {
        "collecting": "Đang trong quá trình thu thập dữ liệu",
        "pending_student_review": "Đã thu thập xong, đang chờ bạn xác nhận",
        "pending_admin_review": "Đã gửi yêu cầu, đang chờ admin phê duyệt",
        "approved": "Đã được phê duyệt",
        "rejected": "Đã bị từ chối, bạn có thể đăng ký lại",
        "cancelled": "Đã hủy, bạn có thể đăng ký lại"
    }
    
    details = {
        "created_at": registration.created_at.isoformat() if registration.created_at else None,
        "student_reviewed_at": registration.student_reviewed_at.isoformat() if registration.student_reviewed_at else None,
        "admin_reviewed_at": registration.admin_reviewed_at.isoformat() if registration.admin_reviewed_at else None,
        "total_images_captured": registration.total_images_captured,
        "registration_progress": registration.registration_progress,
    }
    
    # Add rejection reason if rejected
    if registration.status == "rejected" and registration.rejection_reason:
        details["rejection_reason"] = registration.rejection_reason
    
    return {
        "status": registration.status,
        "registration_id": registration.id,
        "message": status_messages.get(registration.status, "Trạng thái không xác định"),
        "can_register": can_register,
        "details": details
    }


@router.get(
    "/my-status",
    summary="Get current user's face registration status",
    description="Get face registration status for the currently logged-in student."
)
async def get_my_registration_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get face registration status for current user.
    Only works if user is a student.
    """
    # Check if user is a student
    if current_user.role != "student" or not current_user.student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not a student"
        )
    
    # Get student ID from relationship
    student_id = current_user.student.id
    
    return await get_registration_status(
        student_id=student_id,
        db=db,
        current_user=current_user
    )
