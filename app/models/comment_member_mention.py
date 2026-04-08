"""Member mention model for post comments."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class CommentMemberMention(Base):
    """Stores class member mentions detected in comment content."""

    __tablename__ = "comment_member_mentions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comment_id = Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    mentioned_name = Column(String(255), nullable=False)
    mentioned_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    comment = relationship("PostComment", back_populates="member_mentions")
    student = relationship("Student", back_populates="mentioned_in_comments")

    __table_args__ = (
        UniqueConstraint("comment_id", "student_id", name="uq_comment_member_mention"),
        Index("ix_comment_member_mentions_comment_mentioned_at", "comment_id", "mentioned_at"),
    )

    def __repr__(self):
        return f"<CommentMemberMention(id={self.id}, comment_id={self.comment_id}, student_id={self.student_id})>"
