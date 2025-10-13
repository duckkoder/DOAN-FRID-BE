"""Attendance Session model - Represents an attendance taking session for a class."""
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AttendanceSession(BaseModel):
    """Attendance session model for tracking class attendance sessions."""
    
    __tablename__ = "attendance_sessions"
    
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    session_name = Column(String(255), nullable=True)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, nullable=True)
    status = Column(String(50), nullable=False, default="scheduled")  # scheduled, ongoing, finished
    qr_code = Column(Text, nullable=True)
    allow_late_checkin = Column(Boolean, default=True)
    late_threshold_minutes = Column(Integer, default=15)
    location = Column(String(255), nullable=True)
    
    # Relationships
    class_rel = relationship("Class", back_populates="attendance_sessions")
    records = relationship("AttendanceRecord", back_populates="session", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index("ix_attendance_session_class", "class_id"),
        Index("ix_attendance_session_status", "status"),
    )
    
    def __repr__(self):
        return f"<AttendanceSession(id={self.id}, class_id={self.class_id}, status={self.status})>"
