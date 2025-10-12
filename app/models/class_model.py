"""Class model - Represents a course/class taught by a teacher."""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Class(BaseModel):
    """Class model representing a course/class."""
    
    __tablename__ = "classes"
    
    class_name = Column(String(255), nullable=False)
    class_code = Column(String(10), unique=True, nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    description = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    teacher = relationship("Teacher", back_populates="classes")
    schedules = relationship("ClassSchedule", back_populates="class_rel", cascade="all, delete-orphan")
    members = relationship("ClassMember", back_populates="class_rel", cascade="all, delete-orphan")
    attendance_sessions = relationship("AttendanceSession", back_populates="class_rel", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="class_rel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Class(id={self.id}, class_code={self.class_code}, class_name={self.class_name})>"
