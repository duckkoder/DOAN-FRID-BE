"""Document model for source files uploaded for RAG processing."""
import uuid

from sqlalchemy import Column, String, DateTime, Index, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class Document(Base):
    """Document model storing uploaded file metadata."""

    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    course_id = Column(UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    file_url = Column(String(1000), nullable=False)
    uploaded_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    chunks = relationship("DocumentChunk", back_populates="document", cascade="all, delete-orphan")
    post_attachments = relationship("PostAttachment", back_populates="document", cascade="all, delete-orphan")
    post_mentions = relationship("PostDocumentMention", back_populates="document", cascade="all, delete-orphan")
    comment_mentions = relationship("CommentDocumentMention", back_populates="document", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_documents_course_uploaded_at", "course_id", "uploaded_at"),
    )

    def __repr__(self):
        return f"<Document(id={self.id}, course_id={self.course_id}, title={self.title})>"
