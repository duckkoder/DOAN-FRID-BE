"""Class model - Represents a course/class taught by a teacher."""
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Class(BaseModel):
    """Class model representing a course/class."""
    
    __tablename__ = "classes"
    
    class_name = Column(String(255), nullable=False)
    class_code = Column(String(10), unique=True, nullable=False, index=True)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Relationships
    course = relationship("Course", back_populates="classes")
    teacher = relationship("Teacher", back_populates="classes")
    posts = relationship("ClassPost", back_populates="class_rel", cascade="all, delete-orphan")
    schedules = relationship("ClassSchedule", back_populates="class_rel", cascade="all, delete-orphan")
    members = relationship("ClassMember", back_populates="class_rel", cascade="all, delete-orphan")
    attendance_sessions = relationship("AttendanceSession", back_populates="class_rel", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="class_rel", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Class(id={self.id}, class_code={self.class_code}, class_name={self.class_name})>"
