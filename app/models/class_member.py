"""Class Member model - Represents student enrollment in a class."""
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class ClassMember(BaseModel):
    """Class member model representing student enrollment."""
    
    __tablename__ = "class_members"
    
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    joined_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    class_rel = relationship("Class", back_populates="members")
    student = relationship("Student", back_populates="class_members")
    
    # Constraints
    __table_args__ = (
        UniqueConstraint("class_id", "student_id", name="uq_class_student"),
    )
    
    def __repr__(self):
        return f"<ClassMember(id={self.id}, class_id={self.class_id}, student_id={self.student_id})>"
