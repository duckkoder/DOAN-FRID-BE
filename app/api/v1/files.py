"""File upload API endpoints."""
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.services.file_service import FileService


router = APIRouter(prefix="/files", tags=["Files"])


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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload document (private)."""
    file_service = FileService(db)
    
    file_record = await file_service.upload_and_save(
        file=file,
        folder="private/documents",
        uploader_id=current_user.id,
        category="document",
        file_type="document"
    )
    
    # Get presigned URL
    file_url = file_service.get_file_url(file_record.id)
    
    return {
        "success": True,
        "data": {
            "file_id": file_record.id,
            "file_key": file_record.file_key,
            "url": file_url,
            "original_name": file_record.original_name,
            "size": file_record.size,
            "note": "URL expires in 1 hour"
        },
        "message": "Document uploaded successfully"
    }


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
    from app.models.file import File
    
    files = db.query(File).filter(File.uploader_id == current_user.id).all()
    
    file_service = FileService(db)
    
    result = []
    for f in files:
        url = file_service.get_file_url(f.id) if not f.is_public else f"{db.query(File).first()}"
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
