"""Document mention model for post comments."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class CommentDocumentMention(Base):
    """Stores document mentions detected in comment content."""

    __tablename__ = "comment_document_mentions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_title = Column(String(255), nullable=False)
    mentioned_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    comment = relationship("PostComment", back_populates="document_mentions")
    document = relationship("Document", back_populates="comment_mentions")

    __table_args__ = (
        UniqueConstraint("comment_id", "document_id", name="uq_comment_document_mention"),
        Index("ix_comment_document_mentions_comment_mentioned_at", "comment_id", "mentioned_at"),
    )

    def __repr__(self):
        return f"<CommentDocumentMention(id={self.id}, comment_id={self.comment_id}, document_id={self.document_id})>"
