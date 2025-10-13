"""Student model - 1:1 relationship with User."""
from sqlalchemy import Column, Integer, String, Boolean, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Student(BaseModel):
    """Student model with 1:1 relationship to User."""
    
    __tablename__ = "students"
    
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    student_code = Column(String(20), unique=True, nullable=False, index=True)
    date_of_birth = Column(Date, nullable=True)
    major = Column(String(100), nullable=True)
    academic_year = Column(String(10), nullable=True)
    is_verified = Column(Boolean, default=False)
    
    # Relationships
    user = relationship("User", back_populates="student")
    face_embeddings = relationship("FaceEmbedding", back_populates="student", cascade="all, delete-orphan")
    class_members = relationship("ClassMember", back_populates="student", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student", cascade="all, delete-orphan")
    leave_requests = relationship("LeaveRequest", back_populates="student", cascade="all, delete-orphan")
    face_registration_requests = relationship("FaceRegistrationRequest", back_populates="student", cascade="all, delete-orphan")
    face_models = relationship("FaceModel", back_populates="student", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Student(id={self.id}, student_code={self.student_code})>"
