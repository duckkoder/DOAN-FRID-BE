"""Bridge model linking class posts with uploaded documents."""
from sqlalchemy import Column, Integer, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.models.base import Base


class PostAttachment(Base):
    """Bridge table linking class posts and documents."""

    __tablename__ = "post_attachments"

    post_id = Column(Integer, ForeignKey("class_posts.id", ondelete="CASCADE"), primary_key=True)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)

    post = relationship("ClassPost", back_populates="attachments")
    document = relationship("Document", back_populates="post_attachments")

    __table_args__ = (
        Index("ix_post_attachments_document_id", "document_id"),
    )

    def __repr__(self):
        return f"<PostAttachment(post_id={self.post_id}, document_id={self.document_id})>"
