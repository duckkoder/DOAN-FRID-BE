"""Service for managing documents attached to classes or courses."""
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException, status

from app.models.document import Document
from app.models.class_model import Class
from app.models.class_member import ClassMember
from app.models.user import User
from app.models.teacher import Teacher
from app.models.student import Student
from app.core.config import settings

class DocumentService:
    @staticmethod
    def _resolve_document_file_url(document_id: str, file_url: str) -> str:
        """Return a stable backend endpoint for document content."""
        if document_id:
            return f"{settings.BACKEND_BASE_URL}{settings.API_V1_STR}/files/documents/{document_id}/content"
        return file_url

    @staticmethod
    def _ensure_can_access_class_documents(db: Session, user: User, class_id: int) -> Class:
        """Check if user has access to this class's documents."""
        # Find the class
        class_obj = db.query(Class).filter(Class.id == class_id).first()
        if not class_obj:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Class not found")

        if user.role == "teacher":
            teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
            if not teacher or class_obj.teacher_id != teacher.id:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view these documents")
        elif user.role == "student":
            student = db.query(Student).filter(Student.user_id == user.id).first()
            if not student:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to view these documents")
            member = db.query(ClassMember).filter(ClassMember.class_id == class_id, ClassMember.student_id == student.id).first()
            if not member:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You are not a member of this class")
        elif user.role != "admin":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

        return class_obj

    @staticmethod
    def get_class_documents(db: Session, current_user: User, class_id: int) -> dict:
        """Get all documents accessible by the class."""
        class_obj = DocumentService._ensure_can_access_class_documents(db, current_user, class_id)
        
        # Build conditions
        conditions = [Document.only_class_id == class_id]
        if class_obj.course_id:
            conditions.append(
                (Document.course_id == class_obj.course_id) & (Document.only_class_id.is_(None))
            )
            
        # Fetch documents
        documents = db.query(Document).filter(or_(*conditions)).order_by(Document.uploaded_at.desc()).all()
        
        # Map to response schema
        response_data = []
        for doc in documents:
            is_private = doc.only_class_id == class_id
            response_data.append({
                "document_id": str(doc.id),
                "title": doc.title,
                "file_url": DocumentService._resolve_document_file_url(str(doc.id), doc.file_url),
                "created_at": doc.uploaded_at.isoformat() + "Z" if doc.uploaded_at.tzinfo is None else doc.uploaded_at.isoformat(),
                "is_private": is_private
            })
            
        return {
            "success": True,
            "data": response_data,
            "message": "Documents retrieved successfully"
        }
