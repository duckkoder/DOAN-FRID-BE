"""Class Schedule model - Represents weekly schedule for a class."""
from sqlalchemy import Column, Integer, String, ForeignKey, Index, JSON
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ClassSchedule(BaseModel):
    """Class schedule model for weekly class timings."""
    
    __tablename__ = "class_schedules"
    
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    schedule_data = Column(JSON, nullable=False, comment="Weekly schedule: {day: [periods]}")
    
    # Relationships
    class_rel = relationship("Class", back_populates="schedules")
    
    # Indexes
    __table_args__ = (
        Index("ix_class_schedule_class_id", "class_id"),
    )
    
    def __repr__(self):
        return f"<ClassSchedule(id={self.id}, class_id={self.class_id})>"
