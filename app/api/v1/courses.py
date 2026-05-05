"""Course management API endpoints for teachers."""
import asyncio
import httpx
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.class_member import ClassMember
from app.models.class_model import Class
from app.models.course import Course
from app.models.document import Document
from app.models.teacher import Teacher
from app.models.user import User
from app.services.file_service import FileService
from app.schemas.class_schema import DeleteWithPasswordRequest

router = APIRouter(prefix="/teacher/courses", tags=["Course Management"])

_log = logging.getLogger(__name__)


# ── Helpers ────────────────────────────────────────────────────────────────

def _get_teacher(db: Session, current_user: User) -> Teacher:
    if current_user.role != "teacher":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers can access this endpoint")
    teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
    if not teacher:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Teacher profile not found")
    return teacher


def _get_course_owned_by_teacher(db: Session, course_id: UUID, teacher: Teacher) -> Course:
    """Get course owned by this teacher."""
    course = db.query(Course).filter(
        Course.id == course_id,
        Course.teacher_id == teacher.id
    ).first()
    if not course:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found")
    return course


async def _trigger_rag_ingest(doc_id: str, s3_key: str):
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"{settings.AI_SERVICE_URL}/api/v1/rag/ingest",
                json={"document_id": doc_id, "s3_key": s3_key},
                headers={"X-Callback-Secret": settings.AI_SERVICE_SECRET},
            )
            _log.info(f"RAG ingest triggered for {doc_id}: {resp.status_code}")
    except Exception as e:
        _log.warning(f"RAG ingest trigger failed for {doc_id}: {e}")


# ── Schemas ────────────────────────────────────────────────────────────────

class CreateCourseRequest(BaseModel):
    code: str
    title: str
    description: str | None = None


class UpdateCourseRequest(BaseModel):
    title: str | None = None
    description: str | None = None


# ── Course CRUD Endpoints ──────────────────────────────────────────────────

@router.get("")
def list_courses(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get list of courses owned by current teacher."""
    teacher = _get_teacher(db, current_user)

    courses = db.query(Course).filter(
        Course.teacher_id == teacher.id
    ).order_by(Course.created_at.desc()).all()

    result = []
    for course in courses:
        classes_count = db.query(Class).filter(
            Class.course_id == course.id,
            Class.teacher_id == teacher.id
        ).count()
        docs_count = db.query(Document).filter(Document.course_id == course.id).count()
        result.append({
            "id": str(course.id),
            "code": course.code,
            "title": course.title,
            "description": course.description,
            "classesCount": classes_count,
            "documentsCount": docs_count,
            "createdAt": course.created_at.isoformat(),
        })

    return {
        "success": True,
        "data": {
            "courses": result,
            "total": len(result)
        }
    }


@router.post("")
def create_course(
    body: CreateCourseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new academic course."""
    teacher = _get_teacher(db, current_user)

    existing = db.query(Course).filter(
        Course.code == body.code.strip().upper(),
        Course.teacher_id == teacher.id
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"You already have a course with code '{body.code}'")

    course = Course(
        code=body.code.strip().upper(),
        title=body.title.strip(),
        description=body.description,
        teacher_id=teacher.id,
    )
    db.add(course)
    db.commit()
    db.refresh(course)

    return {
        "success": True,
        "message": "Course created successfully",
        "data": {
            "id": str(course.id),
            "code": course.code,
            "title": course.title,
            "description": course.description,
            "createdAt": course.created_at.isoformat(),
        }
    }


@router.get("/{course_id}")
def get_course(
    course_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get course details with its documents."""
    teacher = _get_teacher(db, current_user)
    course = _get_course_owned_by_teacher(db, course_id, teacher)

    # Get documents for this course
    documents = db.query(Document).filter(Document.course_id == course.id).order_by(Document.uploaded_at.desc()).all()
    doc_list = [{
        "id": str(doc.id),
        "title": doc.title,
        "fileUrl": doc.file_url,
        "isEmbedding": doc.is_embedding,
        "onlyClassId": str(doc.only_class_id) if doc.only_class_id else None,
        "uploadedAt": doc.uploaded_at.isoformat(),
    } for doc in documents]

    # Get classes linked to this course
    classes = db.query(Class).filter(
        Class.course_id == course.id,
        Class.teacher_id == teacher.id
    ).all()
    class_list = [{
        "id": str(cls.id) if hasattr(cls.id, 'hex') else cls.id,
        "className": cls.class_name,
        "classCode": cls.class_code,
        "isActive": cls.is_active,
    } for cls in classes]

    return {
        "success": True,
        "data": {
            "id": str(course.id),
            "code": course.code,
            "title": course.title,
            "description": course.description,
            "createdAt": course.created_at.isoformat(),
            "documents": doc_list,
            "classes": class_list,
        }
    }


@router.put("/{course_id}")
def update_course(
    course_id: UUID,
    body: UpdateCourseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update course title/description."""
    teacher = _get_teacher(db, current_user)
    course = _get_course_owned_by_teacher(db, course_id, teacher)

    if body.title is not None:
        course.title = body.title.strip()
    if body.description is not None:
        course.description = body.description

    db.commit()
    db.refresh(course)

    return {
        "success": True,
        "message": "Course updated",
        "data": {"id": str(course.id), "code": course.code, "title": course.title, "description": course.description}
    }


@router.delete("/{course_id}")
def delete_course(
    course_id: UUID,
    payload: DeleteWithPasswordRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a course (cascade deletes documents and unlinks classes) with password verification."""
    from app.core.security import verify_password
    if not verify_password(payload.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Mật khẩu không chính xác")

    teacher = _get_teacher(db, current_user)
    course = _get_course_owned_by_teacher(db, course_id, teacher)

    db.delete(course)
    db.commit()

    return {"success": True, "message": "Course deleted"}


# ── Document Management Endpoints ──────────────────────────────────────────

@router.post("/{course_id}/documents")
async def upload_course_document(
    course_id: UUID,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    is_embedding: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a document to a course (shared across ALL classes in this course).
    - is_embedding: True => AI will index this document for RAG chat.
    - only_class_id is NOT set here (document belongs to the whole course).
    """
    teacher = _get_teacher(db, current_user)
    course = _get_course_owned_by_teacher(db, course_id, teacher)

    file_service = FileService(db)
    file_record = await file_service.upload_and_save(
        file=file,
        folder="public/documents",
        uploader_id=current_user.id,
        category="course_document",
        file_type="document"
    )

    document = Document(
        course_id=course.id,
        only_class_id=None,  # Shared across all classes in this course
        title=title or file_record.original_name or file_record.filename,
        file_url=f"{settings.S3_BASE_URL}/{file_record.file_key}",
        is_embedding=is_embedding,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Trigger RAG ingest only if is_embedding=True
    if is_embedding:
        asyncio.create_task(_trigger_rag_ingest(str(document.id), file_record.file_key))

    return {
        "success": True,
        "message": "Document uploaded to course successfully",
        "data": {
            "id": str(document.id),
            "title": document.title,
            "fileUrl": document.file_url,
            "isEmbedding": document.is_embedding,
            "onlyClassId": None,
            "uploadedAt": document.uploaded_at.isoformat(),
        }
    }


@router.delete("/{course_id}/documents/{document_id}")
def delete_course_document(
    course_id: UUID,
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a document from a course."""
    teacher = _get_teacher(db, current_user)
    _get_course_owned_by_teacher(db, course_id, teacher)

    document = db.query(Document).filter(
        Document.id == document_id,
        Document.course_id == course_id
    ).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found in this course")

    db.delete(document)
    db.commit()

    return {"success": True, "message": "Document deleted"}


# ── Class-specific Document Upload ────────────────────────────────────────

@router.post("/{course_id}/classes/{class_id}/documents")
async def upload_class_private_document(
    course_id: UUID,
    class_id: int,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    is_embedding: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Upload a document PRIVATE to one specific class (only_class_id is set).
    Default behavior: document is private to this class only.
    - is_embedding: True => AI will index this document for RAG chat.
    """
    teacher = _get_teacher(db, current_user)

    # Verify the class belongs to this teacher and this course
    class_obj = db.query(Class).filter(
        Class.id == class_id,
        Class.teacher_id == teacher.id,
        Class.course_id == course_id
    ).first()
    if not class_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Class not found or you don't have permission to upload to this class"
        )

    course = _get_course_owned_by_teacher(db, course_id, teacher)

    file_service = FileService(db)
    file_record = await file_service.upload_and_save(
        file=file,
        folder="public/documents",
        uploader_id=current_user.id,
        category="class_document",
        file_type="document"
    )

    document = Document(
        course_id=course.id,
        only_class_id=class_obj.id,  # Integer class ID
        title=title or file_record.original_name or file_record.filename,
        file_url=f"{settings.S3_BASE_URL}/{file_record.file_key}",
        is_embedding=is_embedding,
    )
    db.add(document)
    db.commit()
    db.refresh(document)

    # Trigger RAG ingest only if is_embedding=True
    if is_embedding:
        asyncio.create_task(_trigger_rag_ingest(str(document.id), file_record.file_key))

    return {
        "success": True,
        "message": "Private class document uploaded successfully",
        "data": {
            "id": str(document.id),
            "title": document.title,
            "fileUrl": document.file_url,
            "isEmbedding": document.is_embedding,
            "onlyClassId": str(document.only_class_id) if document.only_class_id else None,
            "uploadedAt": document.uploaded_at.isoformat(),
        }
    }
