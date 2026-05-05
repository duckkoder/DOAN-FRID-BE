"""Document API endpoints for class document retrieval."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.document_schema import ClassDocumentListResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/classes", tags=["Class Documents"])

@router.get("/{class_id}/documents", response_model=ClassDocumentListResponse)
def get_class_documents(
    class_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get all documents belonging to a class (including private class documents and course-level documents)."""
    result = DocumentService.get_class_documents(db, current_user, class_id)
    return result
