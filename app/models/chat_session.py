"""Chat session model for RAG chatbot memory."""
import uuid

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class ChatSession(Base):
    """Chat session model. Key: (user_id, course_id) — works for both teachers and students."""

    __tablename__ = "chat_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # Changed from student_id → user_id so teachers can also have chat sessions
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Course UUID — sessions are scoped per-course (all classes under same course share history)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)

    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    user = relationship("User", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_chat_sessions_user_course", "user_id", "course_id"),
    )

    def __repr__(self):
        return f"<ChatSession(id={self.id}, user_id={self.user_id}, course_id={self.course_id})>"
