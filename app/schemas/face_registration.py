"""Schemas for Face Registration WebSocket communication."""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, Literal, List
from datetime import datetime


# ============= WebSocket Message Schemas =============

class WSFrameMessage(BaseModel):
    """Message from client containing camera frame."""
    type: Literal["frame"] = "frame"
    data: str = Field(..., description="Base64 encoded image data")


class WSRestartMessage(BaseModel):
    """Message from client to restart verification."""
    type: Literal["restart"] = "restart"


class WSCancelMessage(BaseModel):
    """Message from client to cancel verification."""
    type: Literal["cancel"] = "cancel"


class WSStudentConfirmMessage(BaseModel):
    """Message from client to confirm (accept/reject) collected images."""
    type: Literal["student_confirm"] = "student_confirm"
    accept: bool = Field(..., description="True to accept images, False to reject and re-collect")


# ============= WebSocket Response Schemas =============

class PoseAngles(BaseModel):
    """Face pose angles."""
    pitch: float = Field(..., description="Up/Down tilt in degrees")
    yaw: float = Field(..., description="Left/Right turn in degrees")
    roll: float = Field(..., description="Rotation in degrees")


class BoundingBox(BaseModel):
    """Face bounding box coordinates (normalized 0-1)."""
    x: float = Field(..., description="Top-left X coordinate (normalized)")
    y: float = Field(..., description="Top-left Y coordinate (normalized)")
    width: float = Field(..., description="Width (normalized)")
    height: float = Field(..., description="Height (normalized)")


class FaceLandmark(BaseModel):
    """Single face landmark point (normalized 0-1)."""
    x: float = Field(..., description="X coordinate (normalized)")
    y: float = Field(..., description="Y coordinate (normalized)")
    z: float = Field(..., description="Z coordinate (depth, normalized)")


class WSProcessedFrameResponse(BaseModel):
    """Response with face metadata (NO processed image - client draws on raw video)."""
    type: Literal["processed_frame"] = "processed_frame"
    instruction: str = Field(..., description="Current instruction for user")
    current_step: int = Field(..., description="Current step number (0-indexed)")
    total_steps: int = Field(..., description="Total number of verification steps")
    progress: float = Field(..., description="Progress percentage (0-100)")
    status: Literal["waiting_for_pose", "correct_pose", "capturing"] = Field(
        ..., description="Current status"
    )
    condition_met: bool = Field(..., description="Whether current pose condition is met")
    face_detected: bool = Field(..., description="Whether face is detected in frame")
    pose_angles: Optional[PoseAngles] = Field(None, description="Current face pose angles")
    bounding_box: Optional[BoundingBox] = Field(None, description="Face bounding box (normalized coordinates)")
    landmarks: Optional[List[FaceLandmark]] = Field(None, description="Face mesh landmarks (468 points, normalized)")


class CropInfo(BaseModel):
    """Information about cropped face region."""
    x: int
    y: int
    width: int
    height: int


class WSStepCompletedResponse(BaseModel):
    """Response when a verification step is completed."""
    type: Literal["step_completed"] = "step_completed"
    step_name: str = Field(..., description="Name of completed step")
    step_number: int = Field(..., description="Step number (1-indexed)")
    image_url: Optional[str] = Field(None, description="S3 URL of captured image")
    next_instruction: Optional[str] = Field(None, description="Instruction for next step")
    progress: float = Field(..., description="Overall progress percentage (0-100)")
    pose_angles: PoseAngles = Field(..., description="Pose angles at capture time")


class PreviewImageData(BaseModel):
    """Preview image data for student review."""
    step_name: str = Field(..., description="Step name")
    step_number: int = Field(..., description="Step number (1-indexed)")
    instruction: str = Field(..., description="Instruction text")
    image_base64: str = Field(..., description="Base64 encoded image for preview")
    timestamp: str = Field(..., description="Capture timestamp")
    pose_angles: PoseAngles = Field(..., description="Face pose at capture")


class WSCollectionCompletedResponse(BaseModel):
    """Response when all 14 images are collected, waiting for student review."""
    type: Literal["collection_completed"] = "collection_completed"
    message: str = Field(default="Collection completed! Please review your images.", description="Message")
    total_images: int = Field(..., description="Number of images collected (should be 14)")
    preview_images: list[PreviewImageData] = Field(..., description="All collected images for preview")
    registration_id: int = Field(..., description="Face registration request ID")


class WSStudentConfirmedResponse(BaseModel):
    """Response after student confirms (accept/reject) the images."""
    type: Literal["student_confirmed"] = "student_confirmed"
    accepted: bool = Field(..., description="Whether student accepted the images")
    message: str = Field(..., description="Confirmation message")
    registration_id: Optional[int] = Field(None, description="Registration ID if accepted")
    status: Optional[str] = Field(None, description="New status if accepted")


class VerificationStepData(BaseModel):
    """Data for a single verification step."""
    step: str = Field(..., description="Step name")
    step_number: int = Field(..., description="Step number (1-indexed)")
    instruction: str = Field(..., description="Instruction text")
    image_url: str = Field(..., description="S3 URL of captured image")
    timestamp: datetime = Field(..., description="Capture timestamp")
    pose_angles: PoseAngles = Field(..., description="Face pose at capture")
    face_width: int = Field(..., description="Face width in pixels")
    crop_info: CropInfo = Field(..., description="Crop region information")


class WSRegistrationCompletedResponse(BaseModel):
    """Response when entire registration is completed."""
    type: Literal["registration_completed"] = "registration_completed"
    success: bool = Field(..., description="Whether registration was successful")
    message: str = Field(..., description="Completion message")
    student_id: int = Field(..., description="Student ID")
    registration_id: int = Field(..., description="Face registration request ID")
    total_images: int = Field(..., description="Number of images captured")
    verification_data: list[VerificationStepData] = Field(
        ..., description="All verification steps data"
    )


class WSErrorResponse(BaseModel):
    """Response for errors."""
    type: Literal["error"] = "error"
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class WSStatusResponse(BaseModel):
    """Response with current status."""
    type: Literal["status"] = "status"
    message: str = Field(..., description="Status message")
    current_step: int = Field(..., description="Current step number")
    total_steps: int = Field(..., description="Total steps")
    progress: float = Field(..., description="Progress percentage")


class WSRestartedResponse(BaseModel):
    """Response after restart."""
    type: Literal["restarted"] = "restarted"
    message: str = Field(default="Verification restarted", description="Restart message")


# ============= Database Schemas =============

class FaceRegistrationProgressUpdate(BaseModel):
    """Schema for updating face registration progress."""
    total_images_captured: int = Field(..., ge=0, le=14)
    registration_progress: float = Field(..., ge=0.0, le=100.0)
    verification_data: Optional[Dict[str, Any]] = None


class FaceImageMetadata(BaseModel):
    """Metadata for a captured face image."""
    step_name: str
    step_number: int
    instruction: str
    timestamp: datetime
    pose_angles: PoseAngles
    face_width: int
    crop_info: CropInfo
    s3_key: str  # ✅ Only store S3 key, URLs generated on-demand
    file_size: int


class FaceRegistrationVerificationData(BaseModel):
    """Complete verification data to store in database."""
    verification_date: datetime = Field(default_factory=datetime.utcnow)
    total_steps: int = 14
    completed_steps: int
    success: bool
    steps: list[FaceImageMetadata]


# ============= Error Codes =============

class FaceRegistrationErrorCode:
    """Error codes for face registration."""
    STUDENT_NOT_FOUND = "STUDENT_NOT_FOUND"
    ALREADY_REGISTERED = "ALREADY_REGISTERED"
    ALREADY_PENDING = "ALREADY_PENDING"  # New: student already has pending request
    NO_FACE_DETECTED = "NO_FACE_DETECTED"
    MULTIPLE_FACES = "MULTIPLE_FACES"
    POOR_IMAGE_QUALITY = "POOR_IMAGE_QUALITY"
    S3_UPLOAD_FAILED = "S3_UPLOAD_FAILED"
    DATABASE_ERROR = "DATABASE_ERROR"
    INVALID_FRAME = "INVALID_FRAME"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    WEBSOCKET_ERROR = "WEBSOCKET_ERROR"
    NO_IMAGES_TO_CONFIRM = "NO_IMAGES_TO_CONFIRM"  # New: no preview images available


# ============= Admin API Schemas =============

class FaceRegistrationListItem(BaseModel):
    """Face registration item for list view."""
    id: int
    student_id: int
    student_code: str = Field(..., description="Student code from student table")
    student_name: str = Field(..., description="Student full name")
    student_is_verified: bool = Field(..., description="Student verification status")
    status: str
    total_images_captured: int
    registration_progress: float
    student_reviewed_at: Optional[datetime] = None
    student_accepted: Optional[bool] = None
    admin_reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FaceRegistrationDetailResponse(BaseModel):
    """Detailed face registration response for admin."""
    id: int
    student_id: int
    student_code: str
    student_name: str
    student_email: str
    student_is_verified: bool = Field(..., description="Student verification status")
    status: str
    total_images_captured: int
    registration_progress: float
    verification_data: Optional[Dict[str, Any]] = None
    temp_images_data: Optional[List[Dict[str, Any]]] = None  # ✅ List of temp images, not Dict
    student_reviewed_at: Optional[datetime] = None
    student_accepted: Optional[bool] = None
    admin_reviewed_at: Optional[datetime] = None
    reviewed_by: Optional[int] = None
    reviewer_name: Optional[str] = None
    rejection_reason: Optional[str] = None
    note: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class FaceRegistrationListResponse(BaseModel):
    """Paginated list of face registrations."""
    items: list[FaceRegistrationListItem]
    total: int
    page: int
    limit: int
    total_pages: int


class FaceRegistrationApproveRequest(BaseModel):
    """Request to approve face registration."""
    note: Optional[str] = Field(None, description="Optional admin note")


class FaceRegistrationRejectRequest(BaseModel):
    """Request to reject face registration."""
    rejection_reason: str = Field(..., description="Reason for rejection")
    note: Optional[str] = Field(None, description="Additional admin note")
