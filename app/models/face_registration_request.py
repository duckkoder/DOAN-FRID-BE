"""Face Registration Request model - Workflow for student face registration."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class FaceRegistrationRequest(BaseModel):
    """Face registration request for student face enrollment workflow."""
    
    __tablename__ = "face_registration_requests"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), default="pending")  # pending, approved, rejected
    evidence_file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    note = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="face_registration_requests")
    evidence_file = relationship("File", foreign_keys=[evidence_file_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<FaceRegistrationRequest(id={self.id}, student_id={self.student_id}, status={self.status})>"
