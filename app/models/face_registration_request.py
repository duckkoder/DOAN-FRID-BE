"""Face Registration Request model - Workflow for student face registration."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class FaceRegistrationRequest(BaseModel):
    """Face registration request for student face enrollment workflow.
    
    Status Flow:
    - collecting: Student is collecting 14 images via WebSocket
    - pending_student_review: Collection complete, waiting for student to accept/reject
    - pending_admin_review: Student accepted, waiting for admin approval
    - approved: Admin approved the registration
    - rejected: Rejected by student or admin, can re-collect
    - cancelled: Cancelled by student during collection
    """
    
    __tablename__ = "face_registration_requests"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="collecting")  
    # Status values: collecting, pending_student_review, pending_admin_review, approved, rejected, cancelled
    
    evidence_file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    
    # Student review
    student_reviewed_at = Column(DateTime, nullable=True)
    student_accepted = Column(Boolean, nullable=True)  # True=accepted, False=rejected, None=not reviewed
    
    # Admin review
    admin_reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rejection_reason = Column(Text, nullable=True)  # Reason if rejected by admin
    
    # Face registration progress tracking
    total_images_captured = Column(Integer, default=0, nullable=True)  # 0-14
    registration_progress = Column(Float, default=0.0, nullable=True)  # 0.0-100.0
    verification_data = Column(JSON, nullable=True)  # Stores complete verification metadata
    temp_images_data = Column(JSON, nullable=True)  # Temporary storage for preview images (before student confirm)
    
    # Relationships
    student = relationship("Student", back_populates="face_registration_requests")
    evidence_file = relationship("File", foreign_keys=[evidence_file_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<FaceRegistrationRequest(id={self.id}, student_id={self.student_id}, status={self.status})>"
