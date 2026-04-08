"""Class post model for teacher announcements in a class."""
from sqlalchemy import Column, Integer, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import Base, get_vietnam_time


class ClassPost(Base):
    """Class post model storing teacher announcements/reminders."""

    __tablename__ = "class_posts"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    class_rel = relationship("Class", back_populates="posts")
    teacher = relationship("Teacher", back_populates="class_posts")
    attachments = relationship("PostAttachment", back_populates="post", cascade="all, delete-orphan")
    reactions = relationship("PostReaction", back_populates="post", cascade="all, delete-orphan")
    comments = relationship("PostComment", back_populates="post", cascade="all, delete-orphan")
    document_mentions = relationship("PostDocumentMention", back_populates="post", cascade="all, delete-orphan")
    member_mentions = relationship("PostMemberMention", back_populates="post", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_class_posts_class_created_at", "class_id", "created_at"),
    )

    def __repr__(self):
        return f"<ClassPost(id={self.id}, class_id={self.class_id}, teacher_id={self.teacher_id})>"
