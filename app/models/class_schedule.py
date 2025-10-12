"""Class Schedule model - Represents weekly schedule for a class."""
from sqlalchemy import Column, Integer, SmallInteger, Time, String, ForeignKey, Index
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class ClassSchedule(BaseModel):
    """Class schedule model for weekly class timings."""
    
    __tablename__ = "class_schedules"
    
    class_id = Column(Integer, ForeignKey("classes.id", ondelete="CASCADE"), nullable=False)
    day_of_week = Column(SmallInteger, nullable=False)  # 0=Sunday, 1=Monday, ..., 6=Saturday
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    location = Column(String(255), nullable=True)
    
    # Relationships
    class_rel = relationship("Class", back_populates="schedules")
    
    # Indexes
    __table_args__ = (
        Index("ix_class_schedule_class_day", "class_id", "day_of_week"),
    )
    
    def __repr__(self):
        return f"<ClassSchedule(id={self.id}, class_id={self.class_id}, day={self.day_of_week})>"
