"""Document mention model for class posts."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class PostDocumentMention(Base):
    """Stores document mentions detected in post content."""

    __tablename__ = "post_document_mentions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("class_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    document_title = Column(String(255), nullable=False)
    mentioned_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    post = relationship("ClassPost", back_populates="document_mentions")
    document = relationship("Document", back_populates="post_mentions")

    __table_args__ = (
        UniqueConstraint("post_id", "document_id", name="uq_post_document_mention"),
        Index("ix_post_document_mentions_post_mentioned_at", "post_id", "mentioned_at"),
    )

    def __repr__(self):
        return f"<PostDocumentMention(id={self.id}, post_id={self.post_id}, document_id={self.document_id})>"
