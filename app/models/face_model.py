"""Face Model - Stores trained face recognition models for students."""
from sqlalchemy import Column, Integer, Text, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class FaceModel(BaseModel):
    """Face model storing trained recognition models for students."""
    
    __tablename__ = "face_models"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    model_path = Column(Text, nullable=False)
    vector_dim = Column(Integer, nullable=True)
    accuracy = Column(Float, nullable=True)
    images_count = Column(Integer, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="face_models")
    
    def __repr__(self):
        return f"<FaceModel(id={self.id}, student_id={self.student_id}, accuracy={self.accuracy})>"
