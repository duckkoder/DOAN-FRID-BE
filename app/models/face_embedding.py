"""Face Embedding model - Stores face embeddings for students using pgvector."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import BaseModel


class FaceEmbedding(BaseModel):
    """Face embedding model for storing student face vectors."""
    
    __tablename__ = "face_embeddings"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False)
    image_path = Column(String(255), nullable=False)
    # Note: For production, replace Text with pgvector type:
    # from pgvector.sqlalchemy import Vector
    # embedding = Column(Vector(512), nullable=False)
    embedding = Column(Text, nullable=False)  # Placeholder - use pgvector.Vector(512) in production
    status = Column(String(50), nullable=False, default="pending")  # pending, approved, rejected
    rejection_reason = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="face_embeddings")
    
    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, student_id={self.student_id}, status={self.status})>"
