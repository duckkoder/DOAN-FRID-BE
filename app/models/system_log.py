"""System Log model - Audit trail for system actions."""
from sqlalchemy import Column, Integer, String, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class SystemLog(BaseModel):
    """System log model for audit trail."""
    
    __tablename__ = "system_logs"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(100), nullable=False)
    details = Column(JSON, nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="system_logs")
    
    def __repr__(self):
        return f"<SystemLog(id={self.id}, action={self.action})>"
