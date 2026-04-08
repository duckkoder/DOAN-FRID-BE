"""Post reaction model for emoji reactions on class posts."""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import relationship

from app.models.base import Base, get_vietnam_time


class PostReaction(Base):
    """Stores a teacher/student emoji reaction for a class post."""

    __tablename__ = "post_reactions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    post_id = Column(Integer, ForeignKey("class_posts.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=True, index=True)
    teacher_id = Column(Integer, ForeignKey("teachers.id", ondelete="CASCADE"), nullable=True, index=True)
    emoji = Column(String(32), nullable=False)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)

    post = relationship("ClassPost", back_populates="reactions")
    student = relationship("Student", back_populates="post_reactions")
    teacher = relationship("Teacher", back_populates="post_reactions")

    __table_args__ = (
        CheckConstraint(
            "((student_id IS NOT NULL AND teacher_id IS NULL) OR (student_id IS NULL AND teacher_id IS NOT NULL))",
            name="ck_post_reactions_actor",
        ),
        UniqueConstraint("post_id", "student_id", name="uq_post_reactions_post_student_actor"),
        UniqueConstraint("post_id", "teacher_id", name="uq_post_reactions_post_teacher_actor"),
        Index("ix_post_reactions_post_emoji", "post_id", "emoji"),
    )

    def __repr__(self):
        return (
            f"<PostReaction(id={self.id}, post_id={self.post_id}, "
            f"student_id={self.student_id}, teacher_id={self.teacher_id}, emoji={self.emoji})>"
        )
