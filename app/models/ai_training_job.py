"""AI Training Job model - Tracks AI model training jobs."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class AITrainingJob(BaseModel):
    """AI training job for tracking model training processes."""
    
    __tablename__ = "ai_training_jobs"
    
    config_id = Column(Integer, ForeignKey("model_configs.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="started")  # started, running, completed, failed
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    logs = Column(JSON, nullable=True)
    
    # Relationships
    config = relationship("ModelConfig", back_populates="training_jobs")
    
    def __repr__(self):
        return f"<AITrainingJob(id={self.id}, status={self.status})>"
