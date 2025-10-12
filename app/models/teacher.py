"""Teacher model - 1:1 relationship with User."""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Teacher(BaseModel):
    """Teacher model with 1:1 relationship to User."""
    
    __tablename__ = "teachers"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    teacher_code = Column(String(20), unique=True, nullable=False, index=True)
    department = Column(String(100), nullable=True)
    specialization = Column(String(100), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="teacher")
    classes = relationship("Class", back_populates="teacher", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Teacher(id={self.id}, teacher_code={self.teacher_code})>"
