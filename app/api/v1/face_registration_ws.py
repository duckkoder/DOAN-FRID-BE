"""WebSocket endpoint for real-time face registration.

Handles:
- WebSocket connection management
- Real-time frame processing with MediaPipe
- S3 image upload
- Database updates
- Error handling and rollback
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session
import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from app.database.session import get_db
from app.services.face_verification_service import FaceVerificationService
from app.services.face_registration_service import FaceRegistrationDBService
from app.services.s3_service import s3_service
from app.schemas.face_registration import (
    WSFrameMessage,
    WSRestartMessage,
    WSCancelMessage,
    WSProcessedFrameResponse,
    WSStepCompletedResponse,
    WSRegistrationCompletedResponse,
    WSErrorResponse,
    WSRestartedResponse,
    FaceRegistrationErrorCode,
    FaceImageMetadata,
    FaceRegistrationVerificationData,
    PoseAngles,
    CropInfo,
    VerificationStepData
)
from app.models.face_registration_request import FaceRegistrationRequest
from app.models.file import File

logger = logging.getLogger(__name__)

router = APIRouter()


class FaceRegistrationWebSocketHandler:
    """Handler for face registration WebSocket session."""
    
    def __init__(
        self,
        websocket: WebSocket,
        student_id: int,
        db: Session
    ):
        """Initialize handler."""
        self.websocket = websocket
        self.student_id = student_id
        self.db = db
        
        # Services
        self.face_service = FaceVerificationService()
        self.db_service = FaceRegistrationDBService(db)
        
        # Session state
        self.registration_request: Optional[FaceRegistrationRequest] = None
        self.student: Optional[Any] = None  # Store student object to get user_id
        self.captured_images: List[Dict[str, Any]] = []  # Store captured images with base64 data (before upload)
        self.file_records: List[File] = []
    
    async def send_error(self, error_code: str, message: str, details: Optional[Dict] = None):
        """Send error message to client."""
        try:
            error_response = WSErrorResponse(
                error_code=error_code,
                message=message,
                details=details
            )
            # Use model_dump with mode='json' to properly serialize datetime objects
            await self.websocket.send_json(error_response.model_dump(mode='json'))
        except Exception as e:
            logger.error(f"Failed to send error message: {e}")
    
    async def handle_connection(self):
        """Handle WebSocket connection lifecycle."""
        try:
            # Accept connection
            await self.websocket.accept()
            logger.info(f"WebSocket connected for student {self.student_id}")
            
            # Validate student
            try:
                self.student = self.db_service.validate_student_for_registration(self.student_id)
            except HTTPException as e:
                await self.send_error(
                    FaceRegistrationErrorCode.STUDENT_NOT_FOUND,
                    str(e.detail)
                )
                await self.websocket.close()
                return
            
            # Create/get registration request
            self.registration_request = self.db_service.create_or_get_registration_request(
                student_id=self.student_id
            )
            
            # Send initial status
            await self.websocket.send_json({
                "type": "status",
                "message": "Face registration started",
                "registration_id": self.registration_request.id,
                "current_step": 0,
                "total_steps": 14,
                "progress": 0.0
            })
            
            # Main message loop
            while True:
                try:
                    data = await self.websocket.receive_text()
                    message = json.loads(data)
                    
                    if message["type"] == "frame":
                        await self.handle_frame(message)
                    elif message["type"] == "student_confirm":
                        await self.handle_student_confirm(message)
                    elif message["type"] == "restart":
                        await self.handle_restart()
                    elif message["type"] == "cancel":
                        await self.handle_cancel()
                        break
                    
                except WebSocketDisconnect:
                    logger.info(f"Client disconnected: student {self.student_id}")
                    break
                except json.JSONDecodeError:
                    try:
                        await self.send_error(
                            FaceRegistrationErrorCode.INVALID_FRAME,
                            "Invalid JSON message"
                        )
                    except Exception:
                        logger.error("Failed to send JSON decode error (WebSocket may be closed)")
                        break
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
                    try:
                        await self.send_error(
                            FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                            f"Processing error: {str(e)}"
                        )
                    except Exception:
                        logger.error("Failed to send processing error (WebSocket may be closed)")
                        break
        
        except Exception as e:
            logger.error(f"Fatal error in WebSocket handler: {e}")
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                    f"Connection error: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send fatal error (WebSocket already closed)")
        finally:
            # Cleanup
            await self.cleanup()
    
    async def handle_frame(self, message: Dict[str, Any]):
        """Handle incoming frame from client."""
        try:
            # Decode frame
            frame = self.face_service.decode_base64_frame(message["data"])
            if frame is None:
                await self.send_error(
                    FaceRegistrationErrorCode.INVALID_FRAME,
                    "Failed to decode frame"
                )
                return
            
            # Process frame
            result = self.face_service.process_frame(frame)
            
            # Determine status
            if not result["face_detected"]:
                ws_status = "waiting_for_pose"
            elif result["condition_met"]:
                ws_status = "correct_pose"
            else:
                ws_status = "waiting_for_pose"
            
            # Send processed frame response
            response = WSProcessedFrameResponse(
                image=result["processed_frame"],
                instruction=result["instruction"],
                current_step=result["current_step"],
                total_steps=result["total_steps"],
                progress=round((result["current_step"] / result["total_steps"]) * 100, 2),
                status=ws_status,
                condition_met=result["condition_met"],
                face_detected=result["face_detected"],
                pose_angles=PoseAngles(**result["pose_angles"]) if result["face_detected"] else None
            )
            
            await self.websocket.send_json(response.model_dump(mode='json'))
            
            # If image was captured, store it temporarily (DON'T upload to S3 yet)
            if result["should_capture"]:
                await self.handle_image_capture(result["capture_data"])
            
            # If verification completed, send for student review
            if self.face_service.is_completed():
                await self.send_for_student_review()
        
        except Exception as e:
            logger.error(f"Error handling frame: {e}")
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                    f"Frame processing error: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send frame error (WebSocket may be closed)")
    
    async def handle_image_capture(self, capture_data: Dict[str, Any]):
        """
        Handle captured image - store temporarily (DO NOT upload to S3 yet).
        Upload will happen after student confirms acceptance.
        """
        try:
            # Store capture data in memory
            self.captured_images.append(capture_data)
            
            logger.info(
                f"Captured step {capture_data['step_number']}: "
                f"{capture_data['step_name']} for student {self.student_id} (stored in memory)"
            )
            
            # Send step completed response (without S3 URL)
            progress = self.face_service.get_progress()
            next_step_info = self.face_service.get_current_step_info()
            
            step_response = WSStepCompletedResponse(
                step_name=capture_data["step_name"],
                step_number=capture_data["step_number"],
                image_url=None,  # No S3 URL yet
                next_instruction=next_step_info["instruction"] if next_step_info else None,
                progress=progress["progress_percentage"],
                pose_angles=PoseAngles(**capture_data["pose_angles"])
            )
            
            await self.websocket.send_json(step_response.model_dump(mode='json'))
        
        except Exception as e:
            logger.error(f"Error capturing image: {e}")
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                    f"Failed to capture image: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send capture error (WebSocket may be closed)")
            # Don't stop the process, continue with next step
    
    async def send_for_student_review(self):
        """
        Send collected images to student for review.
        Images are stored temporarily, not uploaded to S3 yet.
        """
        try:
            # Prepare preview images with base64 data
            from app.schemas.face_registration import PreviewImageData, WSCollectionCompletedResponse
            import base64
            
            preview_images = []
            temp_images_data = []  # For DB storage
            
            for capture_data in self.captured_images:
                # Convert image_data (bytes) to base64 string for preview
                image_base64 = base64.b64encode(capture_data["image_data"]).decode('utf-8')
                
                preview_image = PreviewImageData(
                    step_name=capture_data["step_name"],
                    step_number=capture_data["step_number"],
                    instruction=capture_data["instruction"],
                    image_base64=image_base64,
                    timestamp=capture_data["timestamp"],
                    pose_angles=PoseAngles(**capture_data["pose_angles"])
                )
                preview_images.append(preview_image)
                
                # Prepare data for DB temp storage (serialize for JSON)
                temp_data = {
                    "step_name": capture_data["step_name"],
                    "step_number": capture_data["step_number"],
                    "instruction": capture_data["instruction"],
                    "timestamp": capture_data["timestamp"],
                    "pose_angles": capture_data["pose_angles"],
                    "face_width": capture_data["face_width"],
                    "crop_info": capture_data["crop_info"],
                    "image_base64": image_base64  # Store base64 temporarily
                }
                temp_images_data.append(temp_data)
            
            # Save temp data to database
            self.registration_request = self.db_service.save_temp_images(
                registration_id=self.registration_request.id,
                images_data=temp_images_data
            )
            
            # Send collection completed response
            response = WSCollectionCompletedResponse(
                message="Collection completed! Please review your images.",
                total_images=len(preview_images),
                preview_images=preview_images,
                registration_id=self.registration_request.id
            )
            
            await self.websocket.send_json(response.model_dump(mode='json'))
            
            logger.info(
                f"Sent {len(preview_images)} images for student {self.student_id} review, "
                f"registration_id={self.registration_request.id}, status=pending_student_review"
            )
        
        except Exception as e:
            logger.error(f"Error sending for student review: {e}")
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                    f"Failed to prepare review: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send error (WebSocket may be closed)")
    
    async def handle_student_confirm(self, message: Dict[str, Any]):
        """
        Handle student confirmation (accept/reject) of collected images.
        If accepted: upload to S3, create file records, update status to pending_admin_review.
        If rejected: clear temp data, allow re-collection.
        """
        try:
            from app.schemas.face_registration import WSStudentConfirmedResponse
            
            accept = message.get("accept", False)
            
            # Check if registration request exists
            if not self.registration_request:
                await self.send_error(
                    FaceRegistrationErrorCode.SESSION_EXPIRED,
                    "No active registration session"
                )
                return
            
            # Get temp images from database
            if not self.registration_request.temp_images_data:
                await self.send_error(
                    FaceRegistrationErrorCode.NO_IMAGES_TO_CONFIRM,
                    "No images available to confirm"
                )
                return
            
            # Update database with student's decision
            self.registration_request = self.db_service.confirm_by_student(
                registration_id=self.registration_request.id,
                accepted=accept
            )
            
            if accept:
                # Student accepted - upload to S3 and create file records
                logger.info(f"Student {self.student_id} accepted images, uploading to S3...")
                
                temp_images_data = self.registration_request.temp_images_data
                file_metadata_list = []
                
                # Upload each image to S3
                for temp_data in temp_images_data:
                    # Decode base64 back to bytes
                    import base64
                    image_bytes = base64.b64decode(temp_data["image_base64"])
                    
                    # Upload to S3
                    upload_result = await s3_service.upload_face_image(
                        image_data=image_bytes,
                        student_id=self.student_id,
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
                        s3_key=upload_result["file_key"],  # ✅ Only save S3 key
                        file_size=upload_result["file_size"]
                    )
                    file_metadata_list.append(metadata)
                
                # Batch create file records
                self.file_records = self.db_service.batch_create_file_records(
                    uploader_id=self.student.user_id,  # ✅ Use user_id, not student_id
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
                
                # Complete registration (status: pending_admin_review)
                self.registration_request = self.db_service.complete_registration(
                    registration_id=self.registration_request.id,
                    verification_data=verification_data,
                    file_records=self.file_records
                )
                
                # Send success response
                response = WSStudentConfirmedResponse(
                    accepted=True,
                    message="Images accepted and uploaded successfully! Waiting for admin approval.",
                    registration_id=self.registration_request.id,
                    status="pending_admin_review"
                )
                
                await self.websocket.send_json(response.model_dump(mode='json'))
                
                logger.info(
                    f"Student {self.student_id} confirmed registration {self.registration_request.id}, "
                    f"uploaded {len(file_metadata_list)} files, status=pending_admin_review"
                )
            else:
                # Student rejected - allow re-collection
                response = WSStudentConfirmedResponse(
                    accepted=False,
                    message="Images rejected. You can collect new images now.",
                    registration_id=self.registration_request.id,
                    status="rejected"
                )
                
                await self.websocket.send_json(response.model_dump(mode='json'))
                
                # Reset for re-collection
                self.face_service.reset_session()
                self.captured_images.clear()
                
                logger.info(
                    f"Student {self.student_id} rejected images for registration {self.registration_request.id}"
                )
        
        except Exception as e:
            logger.error(f"Error handling student confirm: {e}")
            
            # Rollback if error during upload/save
            await self.rollback_on_error(str(e))
            
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.DATABASE_ERROR,
                    f"Failed to process confirmation: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send error (WebSocket may be closed)")
    
    async def handle_restart(self):
        """Handle restart request - clear captured images and reset."""
        try:
            # Reset verification service
            self.face_service.reset_session()
            
            # Clear captured images (no S3 files to delete since we haven't uploaded yet)
            self.captured_images.clear()
            self.file_records.clear()
            
            # Send restart response
            response = WSRestartedResponse()
            await self.websocket.send_json(response.model_dump(mode='json'))
            
            logger.info(f"Restarted face registration for student {self.student_id}")
        
        except Exception as e:
            logger.error(f"Error restarting: {e}")
            try:
                await self.send_error(
                    FaceRegistrationErrorCode.WEBSOCKET_ERROR,
                    f"Restart failed: {str(e)}"
                )
            except Exception:
                logger.error("Failed to send restart error (WebSocket may be closed)")
    
    async def handle_cancel(self):
        """Handle cancel request - mark as cancelled, no S3 files to delete."""
        try:
            # Cancel registration in database
            if self.registration_request:
                self.db_service.cancel_registration(
                    registration_id=self.registration_request.id,
                    reason="User cancelled"
                )
            
            # No S3 files to delete since we haven't uploaded yet
            
            await self.websocket.send_json({
                "type": "cancelled",
                "message": "Face registration cancelled"
            })
            
            logger.info(f"Cancelled face registration for student {self.student_id}")
        
        except Exception as e:
            logger.error(f"Error cancelling: {e}")
    
    async def rollback_on_error(self, error_message: str):
        """
        Rollback registration on error.
        Note: In new flow, S3 files are only uploaded after student confirms,
        so this method might not need to delete S3 files unless called after confirmation.
        """
        try:
            # Rollback database (will handle file deletion if any exist)
            if self.registration_request:
                self.db_service.rollback_registration(
                    registration_id=self.registration_request.id,
                    file_records=self.file_records,
                    error_message=error_message
                )
            
            # If there are any uploaded S3 files (in case error happened during confirmation)
            # Extract s3_keys from file_records
            if self.file_records:
                s3_keys = [f.file_key for f in self.file_records]
                result = s3_service.batch_delete_files(s3_keys)
                logger.info(f"Rolled back S3 files: {result.get('deleted', 0)} deleted")
        
        except Exception as e:
            logger.error(f"Error during rollback: {e}")
    
    async def cleanup(self):
        """Cleanup resources on connection close."""
        try:
            # Close WebSocket
            await self.websocket.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


@router.websocket("/ws/face-registration/{student_id}")
async def websocket_face_registration(
    websocket: WebSocket,
    student_id: int,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time face registration.
    
    Args:
        student_id: Student ID to register face for
        db: Database session
    
    Protocol:
        Client sends: {"type": "frame", "data": "base64_image"}
        Server sends: {"type": "processed_frame", "image": "...", "instruction": "...", ...}
        Server sends: {"type": "step_completed", "step_name": "...", ...}
        Server sends: {"type": "registration_completed", "success": true, ...}
    """
    handler = FaceRegistrationWebSocketHandler(websocket, student_id, db)
    await handler.handle_connection()
