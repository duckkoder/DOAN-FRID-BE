"""Course model for linking RAG documents to academic courses."""
import uuid

from sqlalchemy import Column, String, Text, DateTime, Integer, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class Course(Base):
    """Course model storing course information."""

    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    documents = relationship("Document", backref="course", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", backref="course", cascade="all, delete-orphan")
    classes = relationship("Class", back_populates="course", cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="courses")

    def __repr__(self):
        return f"<Course(id={self.id}, code={self.code}, title={self.title})>"
