"""Course model for linking RAG documents to academic courses."""
import uuid

from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class Course(Base):
    """Course model storing course information."""

    __tablename__ = "courses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), nullable=False, unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    documents = relationship("Document", backref="course", cascade="all, delete-orphan")
    chat_sessions = relationship("ChatSession", backref="course", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Course(id={self.id}, code={self.code}, title={self.title})>"
