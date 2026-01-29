"""Spoof Detection model - Records detected spoofing attempts during attendance sessions."""
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from zoneinfo import ZoneInfo
from app.models.base import BaseModel


class SpoofDetection(BaseModel):
    """Spoof detection record for logging fake face detection during attendance sessions.
    
    This model stores evidence of spoofing attempts (fake faces, photos, masks, etc.)
    detected by the AI anti-spoofing system during attendance sessions.
    """
    
    __tablename__ = "spoof_detections"
    
    # Foreign keys
    session_id = Column(Integer, ForeignKey("attendance_sessions.id", ondelete="CASCADE"), nullable=False)
    
    # Spoofing information
    spoofing_type = Column(String(50), nullable=False, comment="Type of spoofing detected: 'spoof', 'print', 'replay', 'mask', etc.")
    spoofing_confidence = Column(Float, nullable=False, comment="Confidence score of spoofing detection (0.0 - 1.0)")
    
    # Image evidence
    image_path = Column(String(255), nullable=True, comment="S3 presigned URL to spoof face image")
    
    # Metadata
    detected_at = Column(DateTime(timezone=True), default=lambda: datetime.now(ZoneInfo('Asia/Ho_Chi_Minh')), 
                        comment="Timestamp when spoofing was detected")
    frame_count = Column(Integer, nullable=True, comment="Frame number in which spoofing was detected")
    
    # Relationships
    session = relationship("AttendanceSession", backref="spoof_detections")
    
    # Indexes
    __table_args__ = (
        Index("ix_spoof_detection_session_id", "session_id"),
        Index("ix_spoof_detection_detected_at", "detected_at"),
    )
    
    def __repr__(self):
        return f"<SpoofDetection(id={self.id}, session_id={self.session_id}, spoofing_type={self.spoofing_type}, confidence={self.spoofing_confidence:.2f})>"
