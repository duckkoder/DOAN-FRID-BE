"""Admin API endpoints for managing teachers, students, and system."""
from fastapi import APIRouter, Depends, Query, status, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import base64

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.teacher import TeacherListResponse, TeacherDetailResponse, TeacherUpdateRequest, ResetPasswordRequest as TeacherResetPasswordRequest, ResetPasswordResponse as TeacherResetPasswordResponse
from app.schemas.student import StudentListResponse, StudentDetailResponse, StudentUpdateRequest, ResetPasswordRequest as StudentResetPasswordRequest, ResetPasswordResponse as StudentResetPasswordResponse
from app.schemas.face_registration import (
    FaceRegistrationListResponse,
    FaceRegistrationListItem,
    FaceRegistrationDetailResponse,
    FaceRegistrationApproveRequest,
    FaceRegistrationRejectRequest
)
from app.services.teacher_service import TeacherService
from app.services.student_service import StudentService
from app.services.face_registration_service import FaceRegistrationDBService
from app.services.ai_service_client import AIServiceClient, FaceImageData
from app.services.face_embedding_service import FaceEmbeddingService
from app.services.s3_service import S3Service


router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency to check if user is admin."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied. Admin role required."
        )
    return current_user


@router.get(
    "/teachers",
    response_model=TeacherListResponse,
    summary="Get list of teachers",
    description="Get paginated list of teachers with filters. Admin only."
)
async def get_teachers(
    search: Optional[str] = Query(None, description="Search by name, email, or teacher code"),
    department: Optional[str] = Query(None, description="Filter by department"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get list of teachers with pagination and filters.
    
    - **search**: Search by teacher name, email, or teacher code
    - **department**: Filter by department
    - **is_active**: Filter by active status (true/false)
    - **page**: Page number (starts from 1)
    - **limit**: Number of items per page (max 100)
    """
    skip = (page - 1) * limit
    result = TeacherService.get_teacher_list(
        db=db,
        search=search,
        department=department,
        is_active=is_active,
        skip=skip,
        limit=limit
    )
    return result


@router.get(
    "/teachers/{teacher_id}",
    response_model=TeacherDetailResponse,
    summary="Get teacher by ID",
    description="Get detailed information of a specific teacher. Admin only."
)
async def get_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get teacher details by ID.
    
    - **teacher_id**: Teacher ID
    """
    result = TeacherService.get_teacher_by_id(db=db, teacher_id=teacher_id)
    return result


@router.put(
    "/teachers/{teacher_id}",
    summary="Update teacher information",
    description="Update teacher information. Admin only."
)
async def update_teacher(
    teacher_id: int,
    update_data: TeacherUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update teacher information.
    
    - **teacher_id**: Teacher ID
    - **update_data**: Fields to update (department, specialization, phone, is_active)
    """
    result = TeacherService.update_teacher(
        db=db,
        teacher_id=teacher_id,
        update_data=update_data
    )
    return result


@router.delete(
    "/teachers/{teacher_id}",
    summary="Delete teacher",
    description="Deactivate teacher account. Admin only."
)
async def delete_teacher(
    teacher_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete (deactivate) teacher account.
    
    - **teacher_id**: Teacher ID
    """
    result = TeacherService.delete_teacher(db=db, teacher_id=teacher_id)
    return result


# ============================================================================
# STUDENT ENDPOINTS
# ============================================================================

@router.get(
    "/students",
    response_model=StudentListResponse,
    summary="Get list of students",
    description="Get paginated list of students with filters. Admin only."
)
async def get_students(
    search: Optional[str] = Query(None, description="Search by name, email, or student code"),
    department: Optional[str] = Query(None, description="Filter by department name"),
    academic_year: Optional[str] = Query(None, description="Filter by academic year"),
    is_active: Optional[bool] = Query(None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(None, description="Filter by verification status"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get list of students with pagination and filters.
    
    - **search**: Search by student name, email, or student code
    - **department**: Filter by department name
    - **academic_year**: Filter by academic year (e.g., "2021", "2022")
    - **is_active**: Filter by active status (true/false)
    - **is_verified**: Filter by verification status (true/false)
    - **page**: Page number (starts from 1)
    - **limit**: Number of items per page (max 100)
    """
    skip = (page - 1) * limit
    result = StudentService.get_student_list(
        db=db,
        search=search,
        department=department,
        academic_year=academic_year,
        is_active=is_active,
        is_verified=is_verified,
        skip=skip,
        limit=limit
    )
    return result


@router.get(
    "/students/{student_id}",
    response_model=StudentDetailResponse,
    summary="Get student by ID",
    description="Get detailed information of a specific student. Admin only."
)
async def get_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get student details by ID.
    
    - **student_id**: Student ID
    """
    result = StudentService.get_student_by_id(db=db, student_id=student_id)
    return result


@router.put(
    "/students/{student_id}",
    summary="Update student information",
    description="Update student information. Admin only."
)
async def update_student(
    student_id: int,
    update_data: StudentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Update student information.
    
    - **student_id**: Student ID
    - **update_data**: Fields to update (major, academic_year, date_of_birth, phone, is_active, is_verified)
    """
    result = StudentService.update_student(
        db=db,
        student_id=student_id,
        update_data=update_data
    )
    return result


@router.delete(
    "/students/{student_id}",
    summary="Delete student",
    description="Deactivate student account. Admin only."
)
async def delete_student(
    student_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Delete (deactivate) student account.
    
    - **student_id**: Student ID
    """
    result = StudentService.delete_student(db=db, student_id=student_id)
    return result


# ============================================================================
# FACE REGISTRATION ENDPOINTS
# ============================================================================

@router.get(
    "/face-registrations",
    response_model=FaceRegistrationListResponse,
    summary="Get face registration requests",
    description="Get paginated list of face registration requests. Admin only."
)
async def get_face_registrations(
    status: Optional[str] = Query(None, description="Filter by status (pending_admin_review, approved, rejected)"),
    search: Optional[str] = Query(None, description="Search by student code or name"),
    page: int = Query(1, ge=1, description="Page number"),
    limit: int = Query(10, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get list of face registration requests with filters.
    
    - **status**: Filter by status (pending_admin_review, approved, rejected, etc.)
    - **search**: Search by student code or name
    - **page**: Page number (starts from 1)
    - **limit**: Number of items per page (max 100)
    """
    skip = (page - 1) * limit
    service = FaceRegistrationDBService(db)
    result = service.get_registrations_list(
        status=status,
        search=search,
        skip=skip,
        limit=limit
    )
    
    # Transform to response schema
    items = []
    for reg in result["items"]:
        item = FaceRegistrationListItem(
            id=reg.id,
            student_id=reg.student_id,
            student_code=reg.student.student_code,
            student_name=reg.student.user.full_name,
            student_is_verified=reg.student.is_verified,
            status=reg.status,
            total_images_captured=reg.total_images_captured or 0,
            registration_progress=reg.registration_progress or 0.0,
            student_reviewed_at=reg.student_reviewed_at,
            student_accepted=reg.student_accepted,
            admin_reviewed_at=reg.admin_reviewed_at,
            reviewed_by=reg.reviewed_by,
            created_at=reg.created_at,
            updated_at=reg.updated_at
        )
        items.append(item)
    
    return FaceRegistrationListResponse(
        items=items,
        total=result["total"],
        page=result["page"],
        limit=result["limit"],
        total_pages=result["total_pages"]
    )


@router.get(
    "/face-registrations/{registration_id}",
    response_model=FaceRegistrationDetailResponse,
    summary="Get face registration detail",
    description="Get detailed information of a specific face registration. Admin only."
)
async def get_face_registration(
    registration_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Get face registration details by ID.
    
    - **registration_id**: Face registration request ID
    """
    service = FaceRegistrationDBService(db)
    reg = service.get_registration_detail(registration_id)
    
    # Get reviewer name if exists
    reviewer_name = None
    if reg.reviewed_by:
        from app.models.user import User
        reviewer = db.query(User).filter(User.id == reg.reviewed_by).first()
        if reviewer:
            reviewer_name = reviewer.full_name
    
    # ✅ Generate fresh presigned URLs for images
    verification_data_with_urls = reg.verification_data
    if reg.verification_data and "steps" in reg.verification_data:
        # Extract S3 keys from verification_data
        s3_keys = [step.get("s3_key") for step in reg.verification_data["steps"] if step.get("s3_key")]
        
        if s3_keys:
            from app.services.s3_service import S3Service
            import copy
            s3_service = S3Service()
            
            # Generate fresh presigned URLs (valid for 2 hours)
            presigned_urls = s3_service.batch_generate_presigned_urls(
                file_keys=s3_keys,
                expires_in=7200  # 2 hours for admin review
            )
            
            # Deep copy verification_data to avoid modifying DB object
            verification_data_with_urls = copy.deepcopy(reg.verification_data)
            for step in verification_data_with_urls["steps"]:
                s3_key = step.get("s3_key")
                if s3_key and s3_key in presigned_urls:
                    step["url"] = presigned_urls[s3_key]  # ✅ Fresh URL added dynamically
    
    return FaceRegistrationDetailResponse(
        id=reg.id,
        student_id=reg.student_id,
        student_code=reg.student.student_code,
        student_name=reg.student.user.full_name,
        student_email=reg.student.user.email,
        student_is_verified=reg.student.is_verified,
        status=reg.status,
        total_images_captured=reg.total_images_captured or 0,
        registration_progress=reg.registration_progress or 0.0,
        verification_data=verification_data_with_urls,  # ✅ Contains fresh URLs
        temp_images_data=reg.temp_images_data,
        student_reviewed_at=reg.student_reviewed_at,
        student_accepted=reg.student_accepted,
        admin_reviewed_at=reg.admin_reviewed_at,
        reviewed_by=reg.reviewed_by,
        reviewer_name=reviewer_name,
        rejection_reason=reg.rejection_reason,
        note=reg.note,
        created_at=reg.created_at,
        updated_at=reg.updated_at
    )


@router.post(
    "/face-registrations/{registration_id}/approve",
    summary="Approve face registration",
    description="Approve a face registration request and process embeddings. Admin only."
)
async def approve_face_registration(
    registration_id: int,
    request: FaceRegistrationApproveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Approve a face registration request.
    
    This will:
    1. Download cropped face images from S3
    2. Send images to AI-service for embedding extraction
    3. Save embeddings to face_embeddings table
    4. Update registration status to 'approved'
    
    - **registration_id**: Face registration request ID
    - **note**: Optional admin note
    """
    service = FaceRegistrationDBService(db)
    
    # Get registration details
    reg = service.get_registration_detail(registration_id)
    
    if reg.status != "pending_admin_review":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve registration with status '{reg.status}'. Must be 'pending_admin_review'."
        )
    
    # Verify verification_data exists
    if not reg.verification_data or "steps" not in reg.verification_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No verification data found. Cannot process embeddings."
        )
    
    try:
        # 1. Download images from S3 and prepare for AI service
        s3_service = S3Service()
        face_images = []
        
        for step in reg.verification_data["steps"]:
            s3_key = step.get("s3_key")
            if not s3_key:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Missing S3 key for step {step.get('step_name')}"
                )
            
            # Download image from S3
            image_bytes = await s3_service.download_file(s3_key)
            
            # Convert to base64
            image_base64 = base64.b64encode(image_bytes).decode('utf-8')
            
            # Create FaceImageData
            face_images.append(FaceImageData(
                image_base64=image_base64,
                step_name=step.get("step_name"),
                step_number=step.get("step_number")
            ))
        
        # 2. Call AI service to extract embeddings
        ai_client = AIServiceClient()
        embedding_result = await ai_client.register_face_embeddings(
            student_code=reg.student.student_code,
            student_id=reg.student_id,
            face_images=face_images,
            use_augmentation=True,  # Enable augmentation for better robustness
            augmentation_count=5  # 5 augmented versions per image
        )
        
        if not embedding_result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AI service failed to extract embeddings"
            )
        
        # 3. Save embeddings to database
        embeddings_data = embedding_result.get("embeddings", [])
        
        face_embeddings = FaceEmbeddingService.create_embeddings_batch(
            db=db,
            student_id=reg.student_id,
            student_code=reg.student.student_code,
            embeddings_data=embeddings_data,
            image_prefix="face_registration"
        )
        
        # 4. Update registration status to approved
        reg = service.approve_registration(
            registration_id=registration_id,
            admin_id=current_user.id,
            note=request.note
        )
        
        return {
            "success": True,
            "message": "Face registration approved and embeddings created successfully",
            "registration_id": reg.id,
            "status": reg.status,
            "reviewed_at": reg.admin_reviewed_at,
            "embeddings_created": len(face_embeddings),
            "processing_time_seconds": embedding_result.get("processing_time_seconds", 0)
        }
        
    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        # Log and return error
        import logging
        logger = logging.getLogger(__name__)
        logger.error(
            f"Failed to process face registration approval: {str(e)}",
            extra={
                "registration_id": registration_id,
                "student_id": reg.student_id,
                "error": str(e)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process approval: {str(e)}"
        )


@router.post(
    "/face-registrations/{registration_id}/reject",
    summary="Reject face registration",
    description="Reject a face registration request. Admin only."
)
async def reject_face_registration(
    registration_id: int,
    request: FaceRegistrationRejectRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Reject a face registration request.
    
    - **registration_id**: Face registration request ID
    - **rejection_reason**: Reason for rejection (required)
    - **note**: Optional additional admin note
    """
    service = FaceRegistrationDBService(db)
    reg = service.reject_registration(
        registration_id=registration_id,
        admin_id=current_user.id,
        rejection_reason=request.rejection_reason,
        note=request.note
    )
    
    return {
        "success": True,
        "message": "Face registration rejected",
        "registration_id": reg.id,
        "status": reg.status,
        "rejection_reason": reg.rejection_reason,
        "reviewed_at": reg.admin_reviewed_at
    }


# ============================================================================
# PASSWORD RESET ENDPOINTS
# ============================================================================

@router.post(
    "/teachers/{teacher_id}/reset-password",
    response_model=TeacherResetPasswordResponse,
    summary="Reset teacher password",
    description="Reset password for a specific teacher. Admin only."
)
async def reset_teacher_password(
    teacher_id: int,
    request: TeacherResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Reset teacher password.
    
    - **teacher_id**: Teacher ID
    - **new_password**: New password (min 8 characters, must contain uppercase, lowercase, and digit)
    """
    result = TeacherService.reset_password(
        db=db,
        teacher_id=teacher_id,
        new_password=request.new_password
    )
    return result


@router.post(
    "/students/{student_id}/reset-password",
    response_model=StudentResetPasswordResponse,
    summary="Reset student password",
    description="Reset password for a specific student. Admin only."
)
async def reset_student_password(
    student_id: int,
    request: StudentResetPasswordRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """
    Reset student password.
    
    - **student_id**: Student ID
    - **new_password**: New password (min 8 characters, must contain uppercase, lowercase, and digit)
    """
    result = StudentService.reset_password(
        db=db,
        student_id=student_id,
        new_password=request.new_password
    )
    return result
