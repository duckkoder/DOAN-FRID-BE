"""Repository for Face Embedding operations."""
from typing import List, Dict, Any, Optional
from sqlalchemy import select, and_, func, delete
from sqlalchemy.orm import Session
from app.models.face_embedding import FaceEmbedding
from app.repositories.base import BaseRepository
import numpy as np


class FaceEmbeddingRepository(BaseRepository[FaceEmbedding]):
    """Repository for managing face embeddings with pgvector support."""
    
    def __init__(self, db: Session):
        super().__init__(FaceEmbedding, db)
    
    def get_embeddings_by_student_codes(
        self,
        student_codes: List[str],
        status: str = "approved"
    ) -> List[FaceEmbedding]:
        """
        Get all approved embeddings for a list of student codes.
        This is used for loading session gallery in one query.
        
        Args:
            student_codes: List of student codes (e.g., ['102220312', '102220347', ...])
            status: Status filter (default: 'approved')
        
        Returns:
            List of FaceEmbedding objects with embeddings loaded
        """
        return self.db.query(FaceEmbedding).filter(
            and_(
                FaceEmbedding.student_code.in_(student_codes),
                FaceEmbedding.status == status
            )
        ).order_by(FaceEmbedding.student_code, FaceEmbedding.id).all()
    
    def get_embeddings_by_student_ids(
        self,
        student_ids: List[int],
        status: str = "approved"
    ) -> List[FaceEmbedding]:
        """
        Get all approved embeddings for a list of student IDs.
        Alternative to get_embeddings_by_student_codes.
        
        Args:
            student_ids: List of student IDs
            status: Status filter (default: 'approved')
        
        Returns:
            List of FaceEmbedding objects
        """
        return self.db.query(FaceEmbedding).filter(
            and_(
                FaceEmbedding.student_id.in_(student_ids),
                FaceEmbedding.status == status
            )
        ).order_by(FaceEmbedding.student_id, FaceEmbedding.id).all()
    
    def get_embedding_count_by_student_code(
        self,
        student_code: str,
        status: str = "approved"
    ) -> int:
        """Get count of embeddings for a student."""
        return self.db.query(func.count(FaceEmbedding.id)).filter(
            and_(
                FaceEmbedding.student_code == student_code,
                FaceEmbedding.status == status
            )
        ).scalar() or 0
    
    def get_student_embeddings(
        self,
        student_id: int,
        status: Optional[str] = None
    ) -> List[FaceEmbedding]:
        """Get all embeddings for a specific student."""
        query = self.db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id)
        
        if status:
            query = query.filter(FaceEmbedding.status == status)
        
        return query.order_by(FaceEmbedding.uploaded_at.desc()).all()
    
    def create_embedding(
        self,
        student_id: int,
        student_code: str,
        image_path: str,
        embedding_vector: Any,
        status: str = "approved"
    ) -> FaceEmbedding:
        """
        Create a new face embedding.
        
        Args:
            student_id: Student ID
            student_code: Student code (denormalized for faster queries)
            image_path: Path to the face image
            embedding_vector: Numpy array of shape (512,) or list
            status: Status of the embedding
        
        Returns:
            Created FaceEmbedding object
        """
        # Convert numpy array to list for pgvector
        if isinstance(embedding_vector, np.ndarray):
            embedding_list = embedding_vector.tolist()
        else:
            embedding_list = embedding_vector
        
        face_embedding = FaceEmbedding(
            student_id=student_id,
            student_code=student_code,
            image_path=image_path,
            embedding=embedding_list,
            status=status
        )
        
        self.db.add(face_embedding)
        self.db.commit()
        self.db.refresh(face_embedding)
        
        return face_embedding
    
    def update_embedding_status(
        self,
        embedding_id: int,
        status: str,
        rejection_reason: Optional[str] = None
    ) -> Optional[FaceEmbedding]:
        """Update embedding status (approve/reject)."""
        embedding = self.get(embedding_id)
        if not embedding:
            return None
        
        embedding.status = status
        embedding.rejection_reason = rejection_reason
        
        self.db.commit()
        self.db.refresh(embedding)
        
        return embedding
    
    def delete_student_embeddings(
        self,
        student_id: int
    ) -> int:
        """Delete all embeddings for a student. Returns count of deleted embeddings."""
        embeddings = self.get_student_embeddings(student_id)
        count = len(embeddings)
        
        for embedding in embeddings:
            self.db.delete(embedding)
        
        self.db.commit()
        return count
    
    def search_similar_faces(
        self,
        query_embedding: Any,
        limit: int = 5,
        threshold: float = 0.5,
        status: str = "approved"
    ) -> List[Dict[str, Any]]:
        """
        Search for similar faces using cosine distance.
        Note: This is for general similarity search, not for real-time session matching.
        For session matching, use get_embeddings_by_student_codes to load all embeddings into memory.
        
        Args:
            query_embedding: Query embedding vector (512,) - numpy array or list
            limit: Maximum number of results
            threshold: Cosine distance threshold (lower is more similar)
            status: Status filter
        
        Returns:
            List of dicts with student_id, student_code, distance
        """
        # Convert numpy array to list
        if isinstance(query_embedding, np.ndarray):
            embedding_list = query_embedding.tolist()
        else:
            embedding_list = query_embedding
        
        # Use pgvector's cosine distance operator <=>
        # Note: In SQLAlchemy with pgvector, you need to use func.cosine_distance or raw SQL
        from sqlalchemy import text
        
        query = text("""
            SELECT 
                student_id,
                student_code,
                id as embedding_id,
                embedding <=> CAST(:query_emb AS vector) as distance
            FROM face_embeddings
            WHERE status = :status
            ORDER BY distance
            LIMIT :limit
        """)
        
        result = self.db.execute(
            query,
            {
                'query_emb': str(embedding_list),
                'status': status,
                'limit': limit
            }
        )
        
        rows = result.fetchall()
        
        # Filter by threshold
        return [
            {
                'student_id': row[0],
                'student_code': row[1],
                'embedding_id': row[2],
                'distance': float(row[3]),
                'similarity': 1 - float(row[3])  # Convert distance to similarity
            }
            for row in rows
            if row[3] <= threshold
        ]
