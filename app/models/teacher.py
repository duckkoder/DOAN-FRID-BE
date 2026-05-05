"""Teacher model - 1:1 relationship with User."""
from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Teacher(BaseModel):
    """Teacher model with 1:1 relationship to User."""
    
    __tablename__ = "teachers"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    
    # Foreign Keys to Department and Specialization
    department_id = Column(Integer, ForeignKey("departments.id", ondelete="SET NULL"), nullable=True)
    specialization_id = Column(Integer, ForeignKey("specializations.id", ondelete="SET NULL"), nullable=True)
    
    # Relationships
    user = relationship("User", back_populates="teacher")
    department = relationship("Department", back_populates="teachers")
    specialization = relationship("Specialization", back_populates="teachers")
    classes = relationship("Class", back_populates="teacher", cascade="all, delete-orphan")
    courses = relationship("Course", back_populates="teacher", cascade="all, delete-orphan")
    class_posts = relationship("ClassPost", back_populates="teacher", cascade="all, delete-orphan")
    post_comments = relationship("PostComment", back_populates="teacher", cascade="all, delete-orphan")
    post_reactions = relationship("PostReaction", back_populates="teacher", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Teacher(id={self.id}, user_id={self.user_id})>"
