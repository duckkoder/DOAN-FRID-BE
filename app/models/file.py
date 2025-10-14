"""File model - Manages uploaded files in the system."""
from sqlalchemy import Column, Integer, String, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class File(BaseModel):
    """File model for managing uploads (avatars, face images, evidence files)."""
    
    __tablename__ = "files"
    
    uploader_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # S3 Storage
    file_key = Column(String(500), nullable=False)  # S3 key: "public/avatars/abc123.jpg"
    is_public = Column(Boolean, default=False)  # True if in public/ folder
    
    # File metadata
    filename = Column(String(255), nullable=False)  # Generated filename
    original_name = Column(String(255), nullable=True)  # User's original filename
    mime_type = Column(String(100), nullable=True)
    size = Column(Integer, nullable=True)
    category = Column(String(50), nullable=True)  # avatar, face_image, leave_evidence, etc.
    
    # Relationships
    uploader = relationship("User", back_populates="files")
    attendance_images = relationship("AttendanceImage", back_populates="file", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<File(id={self.id}, filename={self.filename}, category={self.category})>"
