"""File upload API endpoints."""
from uuid import UUID
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, UploadFile, File, Form, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from botocore.exceptions import ClientError

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.class_member import ClassMember
from app.models.class_model import Class
from app.models.document import Document
from app.models.student import Student
from app.models.teacher import Teacher
from app.models.file import File as StoredFile
from app.models.user import User
from app.services.file_service import FileService
from app.services.s3_service import s3_service


router = APIRouter(prefix="/files", tags=["Files"])


def _document_file_key(file_url: str) -> str:
    s3_prefix = f"{settings.S3_BASE_URL}/"
    if file_url.startswith(s3_prefix):
        return file_url[len(s3_prefix):]
    return file_url.lstrip("/")


def _ascii_safe_filename(filename: str | None, fallback: str = "document") -> str:
    normalized = unicodedata.normalize("NFKD", filename or "")
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii").strip()
    ascii_name = re.sub(r"[^a-zA-Z0-9._-]", "_", ascii_name)
    ascii_name = ascii_name.strip("._")
    return ascii_name or fallback


def _class_id_from_course_uuid(course_id: UUID) -> int | None:
    tail = str(course_id).split("-")[-1]
    if not tail.isdigit():
        return None
    try:
        return int(tail)
    except ValueError:
        return None


def _ensure_can_access_document(db: Session, current_user: User, document: Document) -> None:
    class_id = _class_id_from_course_uuid(document.course_id)
    if class_id is None:
        return

    if current_user.role == "teacher":
        teacher = db.query(Teacher).filter(Teacher.user_id == current_user.id).first()
        if not teacher:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can access documents")
        class_obj = db.query(Class).filter(Class.id == class_id, Class.teacher_id == teacher.id).first()
        if not class_obj:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access this document")
        return

    if current_user.role == "student":
        student = db.query(Student).filter(Student.user_id == current_user.id).first()
        if not student:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can access documents")
        member = db.query(ClassMember).filter(ClassMember.class_id == class_id, ClassMember.student_id == student.id).first()
        if not member:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No permission to access this document")
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can access documents")


@router.post("/upload/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload avatar (public)."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder="public/avatars",
        uploader_id=current_user.id,
        category="avatar",
        file_type="image"
    )
    
    # Get URL
    file_url = file_service.get_file_url(file_record.id)
    
    return {
        "success": True,
        "data": {
            "file_id": file_record.id,
            "file_key": file_record.file_key,
            "url": file_url,
            "original_name": file_record.original_name,
            "size": file_record.size
        },
        "message": "Avatar uploaded successfully"
    }


@router.post("/upload/document")
async def upload_document(
    file: UploadFile = File(...),
    course_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload document (private) and optionally register into documents table."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder="public/documents",
        uploader_id=current_user.id,
        category="document",
        file_type="document"
    )
    
    # Get presigned URL
    file_url = file_service.get_file_url(file_record.id)

    document_id = None
    document_title = None
    if course_id:
        try:
            course_uuid = UUID(course_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="course_id must be a valid UUID"
            ) from exc

        document = Document(
            course_id=course_uuid,
            title=title or file_record.original_name or file_record.filename,
            file_url=f"{settings.S3_BASE_URL}/{file_record.file_key}",
        )
        db.add(document)
        db.commit()
        db.refresh(document)

        document_id = str(document.id)
        document_title = document.title

        # ── Trigger RAG ingestion asynchronously ──────────────────────────
        # AI Service reads the file from the shared S3 path.
        # We pass the S3 key so AI Service can download it directly.
        import asyncio, httpx, logging
        _log = logging.getLogger(__name__)

        async def _trigger_ingest(doc_id: str, s3_key: str):
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

        asyncio.create_task(
            _trigger_ingest(document_id, file_record.file_key)
        )
        # ─────────────────────────────────────────────────────────────────
    
    return {
        "success": True,
        "data": {
            "file_id": file_record.id,
            "file_key": file_record.file_key,
            "url": file_url,
            "original_name": file_record.original_name,
            "size": file_record.size,
            "document_id": document_id,
            "document_title": document_title,
            "note": "URL expires in 1 hour"
        },
        "message": "Document uploaded successfully"
    }



@router.get("/documents/{document_id}/content")
async def stream_document_content(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream document content through backend to avoid exposing S3 signed URL in client."""
    document = db.query(Document).filter(Document.id == document_id).first()
    if not document:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    _ensure_can_access_document(db, current_user, document)

    file_key = _document_file_key(document.file_url)
    if not file_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file key not found")

    try:
        obj = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=file_key)
    except ClientError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document file not found")

    content_type = obj.get("ContentType") or "application/octet-stream"
    original_name = (document.title or "document").strip()
    safe_name = _ascii_safe_filename(original_name, fallback="document")
    encoded_name = quote(original_name, safe="")
    headers = {
        "Content-Disposition": f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
    }

    return StreamingResponse(obj["Body"], media_type=content_type, headers=headers)


@router.post("/upload/face")
async def upload_face_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload face image (private)."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder="private/faces",
        uploader_id=current_user.id,
        category="face_image",
        file_type="image"
    )
    
    return {
        "success": True,
        "data": {
            "file_id": file_record.id,
            "file_key": file_record.file_key,
            "original_name": file_record.original_name,
            "size": file_record.size
        },
        "message": "Face image uploaded successfully"
    }


@router.get("/download/{file_id}")
async def get_download_url(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get download URL (presigned for private files)."""
    file_service = FileService(db)
    
    url = file_service.get_file_url(file_id)
    
    return {
        "success": True,
        "data": {
            "file_id": file_id,
            "url": url
        }
    }


@router.delete("/{file_id}")
async def delete_file(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete file."""
    file_service = FileService(db)
    
    file_service.delete_file(file_id, current_user.id)
    
    return {
        "success": True,
        "message": "File deleted successfully"
    }


@router.get("/my-files")
async def get_my_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get files uploaded by current user."""
    files = db.query(StoredFile).filter(StoredFile.uploader_id == current_user.id).all()
    
    file_service = FileService(db)
    
    result = []
    for f in files:
        url = file_service.get_file_url(f.id) if not f.is_public else f"{db.query(StoredFile).first()}"
        result.append({
            "file_id": f.id,
            "filename": f.filename,
            "original_name": f.original_name,
            "category": f.category,
            "size": f.size,
            "is_public": f.is_public,
            "created_at": f.created_at.isoformat()
        })
    
    return {
        "success": True,
        "data": result,
        "total": len(result)
    }
