"""Chat session model for RAG chatbot memory."""
import uuid

from sqlalchemy import Column, Integer, ForeignKey, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class ChatSession(Base):
    """Chat session model."""
    
    __tablename__ = "chat_sessions"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Note: The prompt requested course_id as FK, but since there is no native 'courses' table 
    # mapping to UUIDs in this database schema (only 'classes' map to Integer ids), and the 
    # Document model uses course_id as a UUID column without a foreign key constraint, 
    # we replicate that structure here. If 'course_id' needs to refer to 'classes.id', 
    # it must be an Integer and point to 'classes.id'.
    course_id = Column(UUID(as_uuid=True), nullable=False, index=True) 
    
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)
    
    student = relationship("Student", back_populates="chat_sessions")
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ChatSession(id={self.id}, student_id={self.student_id}, course_id={self.course_id})>"
