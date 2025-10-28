"""
Face Embedding Service - Manage face embeddings in database
"""
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
import numpy as np

from app.models.face_embedding import FaceEmbedding
from app.models.student import Student
from fastapi import HTTPException, status


logger = logging.getLogger(__name__)


class FaceEmbeddingService:
    """Service for managing face embeddings"""
    
    @staticmethod
    def create_embeddings_batch(
        db: Session,
        student_id: int,
        student_code: str,
        embeddings_data: List[Dict[str, Any]],
        image_prefix: str = "face_registration"
    ) -> List[FaceEmbedding]:
        """
        Create multiple face embeddings for a student
        
        Args:
            db: Database session
            student_id: Student ID
            student_code: Student code (denormalized for fast queries)
            embeddings_data: List of dicts with:
                - step_name: str
                - step_number: int
                - embedding: List[float] (512-dim)
            image_prefix: Prefix for image_path
            
        Returns:
            List of created FaceEmbedding objects
            
        Raises:
            HTTPException: If validation fails
        """
        # Verify student exists
        student = db.query(Student).filter(Student.id == student_id).first()
        if not student:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
            )
        
        # Verify student code matches
        if student.student_code != student_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Student code mismatch: expected {student.student_code}, got {student_code}"
            )
        
        created_embeddings = []
        
        try:
            for emb_data in embeddings_data:
                # Validate embedding dimension
                embedding_vector = emb_data.get("embedding", [])
                if len(embedding_vector) != 512:
                    logger.warning(
                        f"Invalid embedding dimension for {emb_data.get('step_name')}: "
                        f"{len(embedding_vector)}, expected 512"
                    )
                    continue
                
                # Create image path (for tracking purposes)
                step_name = emb_data.get("step_name", "unknown")
                step_number = emb_data.get("step_number", 0)
                image_path = f"{image_prefix}/{student_code}/{step_number:02d}_{step_name}.jpg"
                
                # Create embedding record
                face_embedding = FaceEmbedding(
                    student_id=student_id,
                    student_code=student_code,  # Denormalized for fast session queries
                    image_path=image_path,
                    embedding=embedding_vector,  # pgvector handles the conversion
                    status="approved",  # Auto-approved since admin already approved
                    uploaded_at=datetime.utcnow(),
                    reviewed_at=datetime.utcnow()
                )
                
                db.add(face_embedding)
                created_embeddings.append(face_embedding)
                
                logger.debug(
                    f"Created embedding for {student_code}",
                    extra={
                        "step_name": step_name,
                        "step_number": step_number,
                        "embedding_dim": len(embedding_vector)
                    }
                )
            
            # Commit all embeddings
            db.commit()
            
            logger.info(
                f"Successfully created {len(created_embeddings)} embeddings for student {student_code}",
                extra={
                    "student_id": student_id,
                    "student_code": student_code,
                    "total_embeddings": len(created_embeddings)
                }
            )
            
            return created_embeddings
            
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to create embeddings for student {student_code}",
                extra={
                    "student_id": student_id,
                    "error": str(e)
                }
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to save embeddings: {str(e)}"
            )
    
    @staticmethod
    def delete_student_embeddings(
        db: Session,
        student_id: int
    ) -> int:
        """
        Delete all embeddings for a student
        
        Args:
            db: Database session
            student_id: Student ID
            
        Returns:
            Number of deleted embeddings
        """
        try:
            deleted_count = (
                db.query(FaceEmbedding)
                .filter(FaceEmbedding.student_id == student_id)
                .delete(synchronize_session=False)
            )
            
            db.commit()
            
            logger.info(
                f"Deleted {deleted_count} embeddings for student {student_id}"
            )
            
            return deleted_count
            
        except Exception as e:
            db.rollback()
            logger.error(
                f"Failed to delete embeddings for student {student_id}",
                extra={"error": str(e)}
            )
            raise
    
    @staticmethod
    def get_student_embeddings(
        db: Session,
        student_id: int,
        status: Optional[str] = None
    ) -> List[FaceEmbedding]:
        """
        Get all embeddings for a student
        
        Args:
            db: Database session
            student_id: Student ID
            status: Optional filter by status
            
        Returns:
            List of FaceEmbedding objects
        """
        query = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id)
        
        if status:
            query = query.filter(FaceEmbedding.status == status)
        
        return query.order_by(FaceEmbedding.uploaded_at.desc()).all()
    
    @staticmethod
    def count_student_embeddings(
        db: Session,
        student_id: int,
        status: Optional[str] = None
    ) -> int:
        """
        Count embeddings for a student
        
        Args:
            db: Database session
            student_id: Student ID
            status: Optional filter by status
            
        Returns:
            Count of embeddings
        """
        query = db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id)
        
        if status:
            query = query.filter(FaceEmbedding.status == status)
        
        return query.count()
