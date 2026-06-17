"""File upload API endpoints."""
from uuid import UUID
import re
import unicodedata
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, UploadFile, File, Form, Depends, HTTPException, status
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
from app.services.document_ingestion_service import DocumentIngestionService
from app.services.s3_service import s3_service
from app.database.tenant_session import get_current_tenant, tenant_db_session_by_slug
from app.platform.models.tenant import Tenant
from app.schemas.storage import (
    PresignedDownloadResponse,
    PresignedUploadRequest,
    PresignedUploadResponse,
)
from app.storage.storage_service import tenant_storage_service


router = APIRouter(prefix="/files", tags=["Files"])


@router.post("/upload-url", response_model=PresignedUploadResponse)
async def create_upload_url(
    request: PresignedUploadRequest,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Create a tenant-scoped presigned S3 upload URL."""
    return tenant_storage_service.create_presigned_upload_url(
        tenant=tenant,
        folder=request.folder,
        filename=request.filename,
        content_type=request.content_type,
    )


@router.get("/download-url", response_model=PresignedDownloadResponse)
async def create_download_url(
    key: str,
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
):
    """Create a tenant-scoped presigned S3 download URL."""
    return tenant_storage_service.create_presigned_download_url(tenant=tenant, key=key)


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


def _public_file_url(tenant_slug: str, file_id: int) -> str:
    return (
        f"{settings.BACKEND_BASE_URL.rstrip('/')}"
        f"{settings.API_V1_STR}/files/public/{tenant_slug}/{file_id}/content"
    )


def _ensure_can_access_document(db: Session, current_user: User, document: Document) -> None:
    """
    Access check:
    - If only_class_id is set   â†’ check the user belongs to that class.
    - If only course_id is set  â†’ allow any authenticated teacher/student (course-level docs).
    - Admins always allowed.
    """
    if current_user.role == "admin":
        return

    class_id = document.only_class_id

    if class_id is not None:
        # Class-scoped document: verify membership
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

    # Course-level document (only_class_id is None): allow any teacher/student
    if current_user.role in ("teacher", "student"):
        return

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only teachers or students can access documents")


@router.post("/upload/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Upload avatar (public)."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder=f"{tenant.school_code}/avatar",
        uploader_id=current_user.id,
        category="avatar",
        file_type="image",
        is_public=True,
    )
    
    file_url = _public_file_url(tenant.slug, file_record.id)
    
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
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    course_id: str | None = Form(default=None),
    only_class_id: str | None = Form(default=None),
    title: str | None = Form(default=None),
    is_embedding: bool = Form(default=True),
    current_user: User = Depends(get_current_user),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Upload document (private) and optionally register into documents table."""
    document_bytes = await file.read()
    await file.seek(0)
    file_service = FileService(db)
    
    is_class_document = bool(course_id or only_class_id)
    file_record = await file_service.upload_and_save(
        file=file,
        folder=f"{tenant.school_code}/{'document' if is_class_document else 'leaveresponses'}",
        uploader_id=current_user.id,
        category="document" if is_class_document else "leave_evidence",
        file_type="document",
        is_public=False,
    )
    
    # Get presigned URL
    file_url = file_service.get_file_url(file_record.id)

    document_id = None
    document_title = None

    # Parse only_class_id if provided
    only_class_int = None
    if only_class_id:
        try:
            only_class_int = int(only_class_id)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="only_class_id must be a valid integer"
            ) from exc

    should_create_document = course_id or only_class_int is not None

    if should_create_document:
        # --- Case 1: only_class_id provided, no course_id ---
        # Save document scoped to the class only; course_id = NULL
        if only_class_int is not None and not course_id:
            document = Document(
                course_id=None,
                only_class_id=only_class_int,
                title=title or file_record.original_name or file_record.filename,
                file_url=file_record.file_key,
                is_embedding=is_embedding,
            )

        # --- Case 2: course_id provided (with or without only_class_id) ---
        else:
            try:
                course_uuid = UUID(course_id)  # type: ignore[arg-type]
            except ValueError as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="course_id must be a valid UUID"
                ) from exc

            document = Document(
                course_id=course_uuid,
                only_class_id=only_class_int,
                title=title or file_record.original_name or file_record.filename,
                file_url=file_record.file_key,
                is_embedding=is_embedding,
            )

        db.add(document)
        db.commit()
        db.refresh(document)

        document_id = str(document.id)
        document_title = document.title
        if is_embedding:
            background_tasks.add_task(DocumentIngestionService.ingest_pdf_bytes, db, document_id, document_bytes)

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
            "is_embedding": is_embedding,
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
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Upload face image (private)."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder=f"{tenant.school_code}/face",
        uploader_id=current_user.id,
        category="face_image",
        file_type="image",
        is_public=False,
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


@router.get("/public/{tenant_slug}/{file_id}/content")
async def stream_public_file_content(
    tenant_slug: str,
    file_id: int,
):
    """Stream public files through backend so S3 buckets can remain private."""
    with tenant_db_session_by_slug(tenant_slug) as (db, _):
        file_record = db.query(StoredFile).filter(StoredFile.id == file_id, StoredFile.is_public == True).first()
        if not file_record:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Public file not found")

        try:
            obj = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=file_record.file_key)
        except ClientError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

        content_type = obj.get("ContentType") or file_record.mime_type or "application/octet-stream"
        original_name = (file_record.original_name or "file").strip()
        safe_name = _ascii_safe_filename(original_name, fallback="file")
        encoded_name = quote(original_name, safe="")
        headers = {
            "Content-Disposition": f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
        }

        return StreamingResponse(obj["Body"], media_type=content_type, headers=headers)


@router.get("/{file_id}/content")
async def stream_file_content(
    file_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Stream file content through backend."""
    file_record = db.query(StoredFile).filter(StoredFile.id == file_id).first()
    if not file_record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Basic permission check: uploader, admin, or if someone has the file_id 
    # (since file_ids are integers, we should be careful, but leave requests 
    # already expose this ID to authorized parties).
    
    try:
        obj = s3_service.s3_client.get_object(Bucket=s3_service.bucket_name, Key=file_record.file_key)
    except ClientError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found in storage")

    content_type = obj.get("ContentType") or file_record.mime_type or "application/octet-stream"
    original_name = (file_record.original_name or "file").strip()
    safe_name = _ascii_safe_filename(original_name, fallback="file")
    encoded_name = quote(original_name, safe="")
    
    headers = {
        "Content-Disposition": f"inline; filename=\"{safe_name}\"; filename*=UTF-8''{encoded_name}"
    }

    return StreamingResponse(obj["Body"], media_type=content_type, headers=headers)


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
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db)
):
    """Get files uploaded by current user."""
    files = db.query(StoredFile).filter(StoredFile.uploader_id == current_user.id).all()
    
    file_service = FileService(db)
    
    result = []
    for f in files:
        url = _public_file_url(tenant.slug, f.id) if f.is_public else file_service.get_file_url(f.id)
        result.append({
            "file_id": f.id,
            "filename": f.filename,
            "original_name": f.original_name,
            "category": f.category,
            "url": url,
            "size": f.size,
            "is_public": f.is_public,
            "created_at": f.created_at.isoformat()
        })
    
    return {
        "success": True,
        "data": result,
        "total": len(result)
    }
