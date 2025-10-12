"""Attendance Record model - Records individual student attendance."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class AttendanceRecord(BaseModel):
    """Attendance record for individual student attendance."""
    
    __tablename__ = "attendance_records"
    
    session_id = Column(Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    status = Column(String(50), nullable=False, default="absent")  # present, absent, excused
    image_path = Column(String(255), nullable=True)
    confidence_score = Column(Float, nullable=True)
    recorded_at = Column(DateTime, default=datetime.utcnow)
    notes = Column(String(255), nullable=True)
    
    # Relationships
    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("Student", back_populates="attendance_records")
    images = relationship("AttendanceImage", back_populates="record", cascade="all, delete-orphan")
    
    # Constraints and Indexes
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_session_student"),
        Index("ix_attendance_record_recorded_at", "recorded_at"),
    )
    
    def __repr__(self):
        return f"<AttendanceRecord(id={self.id}, session_id={self.session_id}, student_id={self.student_id}, status={self.status})>"
