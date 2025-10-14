from fastapi import UploadFile, HTTPException, status
from sqlalchemy.orm import Session
from typing import Literal

from app.services.s3_service import s3_service
from app.models.file import File
from app.core.config import settings


class FileService:
    """Service for file operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    async def upload_and_save(
        self,
        file: UploadFile,
        folder: Literal["public/avatars", "private/documents", "private/faces"],
        uploader_id: int,
        category: str,
        file_type: Literal["image", "document"] = "image"
    ) -> File:
        """Upload to S3 and save to database."""
        
        # Upload to S3
        s3_result = await s3_service.upload_file(file, folder, file_type)
        
        # Save to DB
        file_record = File(
            uploader_id=uploader_id,
            file_key=s3_result["file_key"],
            filename=s3_result["file_key"].split('/')[-1],
            original_name=file.filename,
            mime_type=file.content_type,
            size=s3_result["file_size"],
            category=category,
            is_public=s3_result["is_public"]
        )
        
        self.db.add(file_record)
        self.db.commit()
        self.db.refresh(file_record)
        
        return file_record
    
    def get_file_url(self, file_id: int) -> str:
        """Get file URL (presigned for private)."""
        file_record = self.db.query(File).filter(File.id == file_id).first()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        if file_record.is_public:
            return f"{settings.S3_BASE_URL}/{file_record.file_key}"
        
        return s3_service.get_presigned_url(file_record.file_key)
    
    def delete_file(self, file_id: int, user_id: int) -> bool:
        """Delete file from S3 and DB."""
        file_record = self.db.query(File).filter(File.id == file_id).first()
        
        if not file_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check permission
        if file_record.uploader_id != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No permission to delete this file"
            )
        
        # Delete from S3
        s3_service.delete_file(file_record.file_key)
        
        # Delete from DB
        self.db.delete(file_record)
        self.db.commit()
        
        return True
