"""Attendance Image model - Multiple captured images per attendance record."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class AttendanceImage(BaseModel):
    """Attendance image for capturing multiple images per attendance record."""
    
    __tablename__ = "attendance_images"
    
    attendance_record_id = Column(Integer, ForeignKey("attendance_records.id", ondelete="CASCADE"), nullable=True)
    file_id = Column(Integer, ForeignKey("files.id", ondelete="SET NULL"), nullable=True)
    captured_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    record = relationship("AttendanceRecord", back_populates="images")
    file = relationship("File", back_populates="attendance_images")
    
    def __repr__(self):
        return f"<AttendanceImage(id={self.id}, attendance_record_id={self.attendance_record_id}, file_id={self.file_id})>"
