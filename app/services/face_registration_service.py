"""Face Registration Database Service.

Handles database operations for face registration workflow:
- Create/update face_registration_requests
- Create file records for captured images
- Transaction management
- Progress tracking
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import HTTPException, status
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.models.face_registration_request import FaceRegistrationRequest
from app.models.file import File
from app.models.student import Student
from app.schemas.face_registration import (
    FaceImageMetadata,
    FaceRegistrationVerificationData,
    FaceRegistrationProgressUpdate
)

logger = logging.getLogger(__name__)


class FaceRegistrationDBService:
    """Service for face registration database operations."""
    
    def __init__(self, db: Session):
        """Initialize with database session."""
        self.db = db
    
    def get_student(self, student_id: int) -> Optional[Student]:
        """Get student by ID."""
        return self.db.query(Student).filter(Student.id == student_id).first()
    
    def validate_student_for_registration(self, student_id: int) -> Student:
        """
        Validate student can register face.
        
        Status Flow:
        - NULL/rejected/cancelled: Can collect (start new or retry)
        - collecting: Can continue (reconnect to existing session)
        - pending_student_review: Cannot collect, must confirm first
        - pending_admin_review: Cannot collect, waiting for admin
        - approved: Cannot collect, already completed
        
        Raises:
            HTTPException: If student not found or has blocking status
        """
        student = self.get_student(student_id)
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
            )
        
        # Check existing registration requests
        existing_request = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.student_id == student_id)
            .order_by(FaceRegistrationRequest.created_at.desc())
            .first()
        )
        
        if existing_request:
            # Block if in certain statuses
            if existing_request.status == "pending_student_review":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "ALREADY_PENDING_STUDENT_REVIEW",
                        "message": "You have collected images waiting for your review. Please confirm or reject them first.",
                        "registration_id": existing_request.id,
                        "status": existing_request.status
                    }
                )
            elif existing_request.status == "pending_admin_review":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "ALREADY_PENDING_ADMIN_REVIEW",
                        "message": "Your face registration is waiting for admin approval. You cannot collect new images.",
                        "registration_id": existing_request.id,
                        "status": existing_request.status,
                        "submitted_at": existing_request.student_reviewed_at.isoformat() if existing_request.student_reviewed_at else None
                    }
                )
            elif existing_request.status == "approved":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "ALREADY_APPROVED",
                        "message": "Your face registration has been approved. You cannot register again.",
                        "registration_id": existing_request.id,
                        "status": existing_request.status,
                        "approved_at": existing_request.admin_reviewed_at.isoformat() if existing_request.admin_reviewed_at else None
                    }
                )
            # Allow if status is: collecting (reconnect), rejected (retry), cancelled (retry)
            logger.info(f"Student {student_id} has existing request with status '{existing_request.status}', allowing collection")
        
        return student
    
    def create_or_get_registration_request(
        self,
        student_id: int,
        force_new: bool = False
    ) -> FaceRegistrationRequest:
        """
        Create new or get existing collecting registration request.
        
        Args:
            student_id: Student ID
            force_new: If True, create new request even if pending exists
        
        Returns:
            FaceRegistrationRequest instance
        """
        if not force_new:
            # Try to get existing collecting request
            existing = (
                self.db.query(FaceRegistrationRequest)
                .filter(
                    FaceRegistrationRequest.student_id == student_id,
                    FaceRegistrationRequest.status == "collecting"
                )
                .first()
            )
            
            if existing:
                logger.info(f"Found existing collecting request {existing.id} for student {student_id}")
                return existing
        
        # Create new request
        registration_request = FaceRegistrationRequest(
            student_id=student_id,
            status="collecting",
            note="Face registration in progress via WebSocket"
        )
        
        self.db.add(registration_request)
        self.db.commit()
        self.db.refresh(registration_request)
        
        logger.info(f"Created new registration request {registration_request.id} for student {student_id}")
        return registration_request
    
    def save_temp_images(
        self,
        registration_id: int,
        images_data: list[Dict[str, Any]]
    ) -> FaceRegistrationRequest:
        """
        Save captured images temporarily for student review.
        
        Args:
            registration_id: Registration request ID
            images_data: List of image data with base64, metadata
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.id == registration_id)
            .first()
        )
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration request {registration_id} not found"
            )
        
        # Save temp data
        registration.temp_images_data = images_data
        registration.status = "pending_student_review"
        registration.total_images_captured = len(images_data)
        registration.registration_progress = 100.0
        
        self.db.commit()
        self.db.refresh(registration)
        
        logger.info(
            f"Saved {len(images_data)} temp images for registration {registration_id}, "
            f"status changed to pending_student_review"
        )
        
        return registration
    
    def confirm_by_student(
        self,
        registration_id: int,
        accepted: bool
    ) -> FaceRegistrationRequest:
        """
        Student confirms (accepts or rejects) the collected images.
        
        Args:
            registration_id: Registration request ID
            accepted: True to accept, False to reject
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.id == registration_id)
            .first()
        )
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration request {registration_id} not found"
            )
        
        if registration.status != "pending_student_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot confirm registration with status '{registration.status}'"
            )
        
        registration.student_reviewed_at = datetime.utcnow()
        registration.student_accepted = accepted
        
        if accepted:
            # Will upload S3 and save files in WebSocket handler
            registration.status = "pending_admin_review"
            registration.note = (registration.note or "") + "\nStudent accepted images"
            logger.info(f"Student accepted registration {registration_id}")
        else:
            # Clear temp data, allow re-collection
            registration.status = "rejected"
            registration.temp_images_data = None
            registration.total_images_captured = 0
            registration.registration_progress = 0.0
            registration.note = (registration.note or "") + "\nStudent rejected images, can re-collect"
            logger.info(f"Student rejected registration {registration_id}")
        
        self.db.commit()
        self.db.refresh(registration)
        
        return registration
    
    def update_registration_progress(
        self,
        registration_id: int,
        progress_data: FaceRegistrationProgressUpdate
    ) -> FaceRegistrationRequest:
        """
        Update registration progress.
        
        Args:
            registration_id: Registration request ID
            progress_data: Progress update data
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.id == registration_id)
            .first()
        )
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration request {registration_id} not found"
            )
        
        # Update fields (need to add these columns to model first)
        # registration.total_images_captured = progress_data.total_images_captured
        # registration.registration_progress = progress_data.registration_progress
        
        # if progress_data.verification_data:
        #     registration.verification_data = progress_data.verification_data
        
        # For now, just update status
        if progress_data.registration_progress >= 100.0:
            registration.status = "completed"
        elif progress_data.registration_progress > 0:
            registration.status = "processing"
        
        self.db.commit()
        self.db.refresh(registration)
        
        logger.info(
            f"Updated registration {registration_id} progress: "
            f"{progress_data.registration_progress}%"
        )
        
        return registration
    
    def create_file_record(
        self,
        uploader_id: int,
        file_key: str,
        file_url: Optional[str],
        filename: str,
        original_name: str,
        file_size: int,
        mime_type: str,
        category: str,
        is_public: bool = False
    ) -> File:
        """
        Create a file record in database.
        
        Args:
            uploader_id: User ID who uploaded
            file_key: S3 key
            file_url: Public URL (if public file)
            filename: Generated filename
            original_name: Original filename
            file_size: File size in bytes
            mime_type: MIME type
            category: File category (e.g., 'face_registration')
            is_public: Whether file is publicly accessible
        
        Returns:
            Created File instance
        """
        file_record = File(
            uploader_id=uploader_id,
            file_key=file_key,
            is_public=is_public,
            filename=filename,
            original_name=original_name,
            mime_type=mime_type,
            size=file_size,
            category=category
        )
        
        self.db.add(file_record)
        self.db.flush()  # Don't commit yet, part of larger transaction
        
        logger.info(f"Created file record {file_record.id}: {filename}")
        return file_record
    
    def batch_create_file_records(
        self,
        uploader_id: int,
        file_metadata_list: List[FaceImageMetadata],
        category: str = "face_registration"
    ) -> List[File]:
        """
        Batch create file records for face images.
        
        Args:
            uploader_id: User ID
            file_metadata_list: List of file metadata
            category: File category
        
        Returns:
            List of created File instances
        """
        file_records = []
        
        for metadata in file_metadata_list:
            file_record = File(
                uploader_id=uploader_id,
                file_key=metadata.s3_key,
                is_public=False,  # Face images are private
                filename=f"{metadata.step_name}.jpg",
                original_name=f"{metadata.step_name}_{metadata.step_number}.jpg",
                mime_type="image/jpeg",
                size=metadata.file_size,
                category=category
            )
            
            self.db.add(file_record)
            file_records.append(file_record)
        
        self.db.flush()
        
        logger.info(f"Batch created {len(file_records)} file records for user {uploader_id}")
        return file_records
    
    def complete_registration(
        self,
        registration_id: int,
        verification_data: FaceRegistrationVerificationData,
        file_records: List[File]
    ) -> FaceRegistrationRequest:
        """
        Complete registration after student accepted and files uploaded.
        Status should already be 'pending_admin_review'.
        
        Args:
            registration_id: Registration request ID
            verification_data: Complete verification data
            file_records: List of created file records
        
        Returns:
            Updated FaceRegistrationRequest
        """
        try:
            registration = (
                self.db.query(FaceRegistrationRequest)
                .filter(FaceRegistrationRequest.id == registration_id)
                .first()
            )
            
            if not registration:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Registration request {registration_id} not found"
                )
            
            # Update registration (keep status as pending_admin_review)
            # Use model_dump(mode='json') to properly serialize datetime objects
            registration.verification_data = verification_data.model_dump(mode='json')
            registration.total_images_captured = verification_data.completed_steps
            registration.registration_progress = 100.0
            
            # Clear temp data since we've uploaded to S3
            registration.temp_images_data = None
            
            # Link first file as evidence (optional)
            if file_records:
                registration.evidence_file_id = file_records[0].id
            
            self.db.commit()
            self.db.refresh(registration)
            
            logger.info(
                f"Completed registration {registration_id} with "
                f"{len(file_records)} files, status: {registration.status}"
            )
            
            return registration
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to complete registration {registration_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: {str(e)}"
            )
    
    def cancel_registration(
        self,
        registration_id: int,
        reason: str = "User cancelled"
    ) -> FaceRegistrationRequest:
        """
        Cancel a registration request.
        
        Args:
            registration_id: Registration request ID
            reason: Cancellation reason
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.id == registration_id)
            .first()
        )
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration request {registration_id} not found"
            )
        
        registration.status = "rejected"
        registration.note = f"{registration.note or ''}\nCancelled: {reason}"
        
        self.db.commit()
        self.db.refresh(registration)
        
        logger.info(f"Cancelled registration {registration_id}: {reason}")
        return registration
    
    def delete_file_records(self, file_ids: List[int]) -> int:
        """
        Delete file records by IDs.
        
        Args:
            file_ids: List of file IDs to delete
        
        Returns:
            Number of deleted records
        """
        try:
            deleted_count = (
                self.db.query(File)
                .filter(File.id.in_(file_ids))
                .delete(synchronize_session=False)
            )
            
            self.db.commit()
            logger.info(f"Deleted {deleted_count} file records")
            return deleted_count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Failed to delete file records: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete files: {str(e)}"
            )
    
    def rollback_registration(
        self,
        registration_id: int,
        file_records: List[File],
        error_message: str
    ) -> None:
        """
        Rollback registration on error.
        
        Args:
            registration_id: Registration request ID
            file_records: File records to delete
            error_message: Error message to log
        """
        try:
            # Delete file records
            if file_records:
                file_ids = [f.id for f in file_records]
                self.delete_file_records(file_ids)
            
            # Update registration status
            registration = (
                self.db.query(FaceRegistrationRequest)
                .filter(FaceRegistrationRequest.id == registration_id)
                .first()
            )
            
            if registration:
                registration.status = "rejected"
                registration.note = f"Failed: {error_message}"
                self.db.commit()
            
            logger.info(f"Rolled back registration {registration_id}")
            
        except Exception as e:
            logger.error(f"Failed to rollback registration {registration_id}: {e}")
            self.db.rollback()
    
    # ============= Admin Methods =============
    
    def get_registrations_list(
        self,
        status: Optional[str] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Get paginated list of face registration requests.
        
        Args:
            status: Filter by status
            search: Search by student code or name
            skip: Number of records to skip
            limit: Number of records to return
        
        Returns:
            Dict with items and pagination info
        """
        from sqlalchemy import or_
        
        query = self.db.query(FaceRegistrationRequest).join(Student)
        
        # Apply filters
        if status:
            query = query.filter(FaceRegistrationRequest.status == status)
        
        if search:
            query = query.filter(
                or_(
                    Student.student_code.ilike(f"%{search}%"),
                    Student.full_name.ilike(f"%{search}%")
                )
            )
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        registrations = (
            query
            .order_by(FaceRegistrationRequest.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        
        # Calculate total pages
        total_pages = (total + limit - 1) // limit if limit > 0 else 0
        
        return {
            "items": registrations,
            "total": total,
            "page": (skip // limit) + 1 if limit > 0 else 1,
            "limit": limit,
            "total_pages": total_pages
        }
    
    def get_registration_detail(self, registration_id: int) -> FaceRegistrationRequest:
        """
        Get detailed face registration by ID.
        
        Args:
            registration_id: Registration request ID
        
        Returns:
            FaceRegistrationRequest with joined data
        """
        registration = (
            self.db.query(FaceRegistrationRequest)
            .filter(FaceRegistrationRequest.id == registration_id)
            .first()
        )
        
        if not registration:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Registration request {registration_id} not found"
            )
        
        return registration
    
    def approve_registration(
        self,
        registration_id: int,
        admin_id: int,
        note: Optional[str] = None
    ) -> FaceRegistrationRequest:
        """
        Approve face registration request.
        
        Args:
            registration_id: Registration request ID
            admin_id: Admin user ID
            note: Optional admin note
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = self.get_registration_detail(registration_id)
        
        if registration.status != "pending_admin_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot approve registration with status '{registration.status}'. Must be 'pending_admin_review'."
            )
        
        registration.status = "approved"
        registration.admin_reviewed_at = datetime.utcnow()
        registration.reviewed_by = admin_id
        if note:
            registration.note = (registration.note or "") + f"\nAdmin note: {note}"
        
        self.db.commit()
        self.db.refresh(registration)
        
        logger.info(f"Admin {admin_id} approved registration {registration_id}")
        return registration
    
    def reject_registration(
        self,
        registration_id: int,
        admin_id: int,
        rejection_reason: str,
        note: Optional[str] = None
    ) -> FaceRegistrationRequest:
        """
        Reject face registration request.
        
        Args:
            registration_id: Registration request ID
            admin_id: Admin user ID
            rejection_reason: Reason for rejection
            note: Optional admin note
        
        Returns:
            Updated FaceRegistrationRequest
        """
        registration = self.get_registration_detail(registration_id)
        
        if registration.status != "pending_admin_review":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot reject registration with status '{registration.status}'. Must be 'pending_admin_review'."
            )
        
        registration.status = "rejected"
        registration.admin_reviewed_at = datetime.utcnow()
        registration.reviewed_by = admin_id
        registration.rejection_reason = rejection_reason
        if note:
            registration.note = (registration.note or "") + f"\nAdmin note: {note}"
        
        self.db.commit()
        self.db.refresh(registration)
        
        logger.info(f"Admin {admin_id} rejected registration {registration_id}: {rejection_reason}")
        return registration
