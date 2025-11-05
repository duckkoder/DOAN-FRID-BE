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
    # None means no active registration (can register)
    can_register = registration.status in [None, "rejected", "cancelled", "collecting"]
    
    # Build response based on status
    status_messages = {
        None: "Chưa có đăng ký nào đang hoạt động, bạn có thể đăng ký mới",
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


@router.get(
    "/load-pending-review",
    summary="Load pending review images",
    description="Load temporary images for pending student review"
)
async def load_pending_review_images(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Load temporary images when student needs to review.
    Only works for pending_student_review status.
    """
    # Check if user is a student
    if current_user.role != "student" or not current_user.student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not a student"
        )
    
    student_id = current_user.student.id
    
    # Get most recent registration with pending_student_review status
    from app.models.face_registration_request import FaceRegistrationRequest
    registration = (
        db.query(FaceRegistrationRequest)
        .filter(
            FaceRegistrationRequest.student_id == student_id,
            FaceRegistrationRequest.status == "pending_student_review"
        )
        .order_by(FaceRegistrationRequest.created_at.desc())
        .first()
    )
    
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review found"
        )
    
    # Load temp data from JSON field
    if not registration.temp_images_data or not isinstance(registration.temp_images_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No temporary data available"
        )
    
    captured_images = registration.temp_images_data.get("captured_images", [])
    
    if not captured_images:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No images found in temporary data"
        )
    
    return {
        "registration_id": registration.id,
        "status": registration.status,
        "total_images": len(captured_images),
        "preview_images": captured_images,
        "message": "Loaded temporary images for review"
    }


@router.post(
    "/confirm-pending-review",
    summary="Confirm pending review images",
    description="Student confirms or rejects temporarily stored images"
)
async def confirm_pending_review(
    accept: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Confirm or reject pending review images.
    If accepted: upload to S3 and change status to pending_admin_review
    If rejected: delete temp data and change status to can_register
    """
    # Check if user is a student
    if current_user.role != "student" or not current_user.student:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current user is not a student"
        )
    
    student_id = current_user.student.id
    
    # Get most recent registration with pending_student_review status
    from app.models.face_registration_request import FaceRegistrationRequest
    from app.core.logging import logger
    
    registration = (
        db.query(FaceRegistrationRequest)
        .filter(
            FaceRegistrationRequest.student_id == student_id,
            FaceRegistrationRequest.status == "pending_student_review"
        )
        .order_by(FaceRegistrationRequest.created_at.desc())
        .first()
    )
    
    logger.info(f"Student {student_id} confirm (accept={accept}) - found registration: {registration is not None}")
    if registration:
        logger.info(f"Registration ID: {registration.id}, status: {registration.status}")
        logger.info(f"temp_images_data type: {type(registration.temp_images_data)}")
        if isinstance(registration.temp_images_data, dict):
            logger.info(f"temp_images_data keys: {registration.temp_images_data.keys()}")
    
    if not registration:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No pending review found"
        )
    
    if accept:
        # Student accepted - upload to S3 and move to pending_admin_review
        from datetime import datetime
        from app.services.s3_service import S3Service
        from app.schemas.face_registration import FaceImageMetadata, PoseAngles, CropInfo, FaceRegistrationVerificationData
        import base64
        
        db_service = FaceRegistrationDBService(db)
        s3_service = S3Service()
        
        # Extract images from temp data
        temp_images_data = registration.temp_images_data
        if isinstance(temp_images_data, dict):
            captured_images = temp_images_data.get("captured_images", [])
        else:
            captured_images = temp_images_data
        
        if not captured_images:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No images found in temporary data"
            )
        
        # Upload images to S3 and create file records
        try:
            file_metadata_list = []
            
            for temp_data in captured_images:
                # Decode base64 to bytes
                image_bytes = base64.b64decode(temp_data["image_base64"])
                
                # Upload to S3
                upload_result = await s3_service.upload_face_image(
                    image_data=image_bytes,
                    student_id=student_id,
                    step_name=temp_data["step_name"],
                    step_number=temp_data["step_number"],
                    metadata=temp_data["pose_angles"]
                )
                
                # Create metadata for file record
                metadata = FaceImageMetadata(
                    step_name=temp_data["step_name"],
                    step_number=temp_data["step_number"],
                    instruction=temp_data["instruction"],
                    timestamp=datetime.fromisoformat(temp_data["timestamp"]),
                    pose_angles=PoseAngles(**temp_data["pose_angles"]),
                    face_width=temp_data["face_width"],
                    crop_info=CropInfo(**temp_data["crop_info"]),
                    s3_key=upload_result["file_key"],
                    file_size=upload_result["file_size"]
                )
                file_metadata_list.append(metadata)
            
            # Batch create file records
            file_records = db_service.batch_create_file_records(
                uploader_id=current_user.student.user_id,
                file_metadata_list=file_metadata_list,
                category="face_registration"
            )
            
            # Prepare verification data
            verification_data = FaceRegistrationVerificationData(
                verification_date=datetime.utcnow(),
                total_steps=14,
                completed_steps=len(file_metadata_list),
                success=True,
                steps=file_metadata_list
            )
            
            # Complete registration
            registration = db_service.complete_registration(
                registration_id=registration.id,
                verification_data=verification_data,
                file_records=file_records
            )
            
            return {
                "success": True,
                "status": "pending_admin_review",
                "message": "Ảnh đã được xác nhận và gửi cho admin duyệt",
                "total_images": len(file_records)
            }
            
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload images: {str(e)}"
            )
    else:
        # Student rejected - clear temp data and reset to can_register
        registration.temp_images_data = None
        registration.status = None  # Reset to allow new registration
        
        db.commit()
        
        return {
            "success": True,
            "status": None,
            "message": "Đã hủy ảnh. Bạn có thể thu thập lại."
        }


