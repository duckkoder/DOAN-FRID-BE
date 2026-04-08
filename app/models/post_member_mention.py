"""Member mention model for class posts."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class PostMemberMention(Base):
    """Stores class member mentions detected in post content."""

    __tablename__ = "post_member_mentions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("class_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    mentioned_name = Column(String(255), nullable=False)
    mentioned_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    post = relationship("ClassPost", back_populates="member_mentions")
    student = relationship("Student", back_populates="mentioned_in_posts")

    __table_args__ = (
        UniqueConstraint("post_id", "student_id", name="uq_post_member_mention"),
        Index("ix_post_member_mentions_post_mentioned_at", "post_id", "mentioned_at"),
    )

    def __repr__(self):
        return f"<PostMemberMention(id={self.id}, post_id={self.post_id}, student_id={self.student_id})>"
