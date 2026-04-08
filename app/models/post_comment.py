"""Post comment model for class post discussions."""
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index, CheckConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class PostComment(Base):
    """Stores student/teacher comments on class posts."""

    __tablename__ = "post_comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("class_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)
    parent_comment_id = Column(Integer, ForeignKey("post_comments.id", ondelete="CASCADE"), nullable=True, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    post = relationship("ClassPost", back_populates="comments")
    student = relationship("Student", back_populates="post_comments")
    teacher = relationship("Teacher", back_populates="post_comments")
    parent_comment = relationship("PostComment", remote_side=[id], back_populates="replies")
    replies = relationship("PostComment", back_populates="parent_comment", cascade="all, delete-orphan")
    document_mentions = relationship("CommentDocumentMention", back_populates="comment", cascade="all, delete-orphan")
    member_mentions = relationship("CommentMemberMention", back_populates="comment", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "((student_id IS NOT NULL AND teacher_id IS NULL) OR (student_id IS NULL AND teacher_id IS NOT NULL))",
            name="ck_post_comments_actor",
        ),
        Index("ix_post_comments_post_created_at", "post_id", "created_at"),
        Index("ix_post_comments_parent_created_at", "parent_comment_id", "created_at"),
    )

    def __repr__(self):
        return (
            f"<PostComment(id={self.id}, post_id={self.post_id}, "
            f"student_id={self.student_id}, teacher_id={self.teacher_id})>"
        )
