"""Face Embedding model - Stores face embeddings for students using pgvector."""
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Index
from sqlalchemy.orm import relationship
from datetime import datetime
from pgvector.sqlalchemy import Vector
from app.models.base import BaseModel


class FaceEmbedding(BaseModel):
    """Face embedding model for storing student face vectors."""
    
    __tablename__ = "face_embeddings"
    
    student_id = Column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    student_code = Column(String(20), nullable=False, index=True)  # Denormalized for faster session queries
    image_path = Column(String(255), nullable=False)
    embedding = Column(Vector(512), nullable=False)  # pgvector for similarity search
    status = Column(String(50), nullable=False, default="approved")  # pending, approved, rejected
    rejection_reason = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)
    
    # Relationships
    student = relationship("Student", back_populates="face_embeddings")
    
    # Index for vector similarity search using cosine distance
    __table_args__ = (
        Index(
            'idx_face_embeddings_vector_cosine',
            'embedding',
            postgresql_using='ivfflat',
            postgresql_with={'lists': 100},
            postgresql_ops={'embedding': 'vector_cosine_ops'}
        ),
    )
    
    def __repr__(self):
        return f"<FaceEmbedding(id={self.id}, student_id={self.student_id}, student_code={self.student_code}, status={self.status})>"
