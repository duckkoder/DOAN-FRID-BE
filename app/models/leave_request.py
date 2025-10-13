"""Leave Request model - Student leave/absence requests."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class LeaveRequest(BaseModel):
    """Leave request model for student absence requests."""
    
    __tablename__ = "leave_requests"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    reason = Column(Text, nullable=False)
    leave_dates = Column(JSON, nullable=False)  # [{date, reason}, ...]
    evidence_file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected, cancelled
    reviewed_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    review_notes = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="leave_requests")
    class_rel = relationship("Class", back_populates="leave_requests")
    evidence_file = relationship("File", foreign_keys=[evidence_file_id])
    reviewer = relationship("User", foreign_keys=[reviewed_by])
    
    def __repr__(self):
        return f"<LeaveRequest(id={self.id}, student_id={self.student_id}, status={self.status})>"
