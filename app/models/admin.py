"""Admin model - 1:1 relationship with User."""
from sqlalchemy import Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Admin(BaseModel):
    """Admin model with 1:1 relationship to User."""
    
    __tablename__ = "admins"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="admin")
    model_configs = relationship("ModelConfig", back_populates="created_by_admin", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Admin(id={self.id}, user_id={self.user_id})>"
