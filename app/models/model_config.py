"""Model Config - AI model configuration settings."""
from sqlalchemy import Column, Integer, String, Float, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ModelConfig(BaseModel):
    """Model configuration for AI face recognition settings."""
    
    __tablename__ = "model_configs"
    
    config_name = Column(String(100), unique=True, nullable=False, index=True)
    face_detection_confidence = Column(Float, default=0.7)
    face_detection_iou = Column(Float, default=0.45)
    face_recognition_threshold = Column(Float, default=0.6)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("admins.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    created_by_admin = relationship("Admin", back_populates="model_configs")
    training_jobs = relationship("AITrainingJob", back_populates="config", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ModelConfig(id={self.id}, config_name={self.config_name})>"
