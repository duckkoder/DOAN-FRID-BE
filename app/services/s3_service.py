"""AWS S3 Service for file uploads."""
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from fastapi import UploadFile, HTTPException, status
from typing import Literal
import uuid
from datetime import datetime

from app.core.config import settings


class S3Service:
    """AWS S3 Service."""
    
    def __init__(self):
        """Initialize S3 client."""
        try:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                region_name=settings.AWS_REGION
            )
            self.bucket_name = settings.AWS_S3_BUCKET_NAME
        except NoCredentialsError:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="AWS credentials not found"
            )
    
    def _validate_file(self, file: UploadFile, file_type: Literal["image", "document"]) -> None:
        """Validate file size and extension."""
        # Check size
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)
        
        if file_size > settings.MAX_FILE_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File exceeds {settings.MAX_FILE_SIZE_MB}MB limit"
            )
        
        # Check extension
        file_ext = file.filename.split('.')[-1].lower()
        allowed = (
            settings.ALLOWED_IMAGE_EXTENSIONS_LIST if file_type == "image"
            else settings.ALLOWED_DOCUMENT_EXTENSIONS_LIST
        )
        
        if file_ext not in allowed:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Extension .{file_ext} not allowed"
            )
    
    async def upload_file(
        self,
        file: UploadFile,
        folder: Literal["public/avatars", "private/documents", "private/faces"],
        file_type: Literal["image", "document"] = "image"
    ) -> dict:
        """Upload file to S3."""
        
        # Validate
        self._validate_file(file, file_type)
        
        # Generate unique filename
        file_ext = file.filename.split('.')[-1].lower()
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        unique_id = str(uuid.uuid4())
        new_filename = f"{timestamp}_{unique_id}.{file_ext}"
        s3_key = f"{folder}/{new_filename}"
        
        # Read content
        file_content = await file.read()
        
        # Upload
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=file_content,
                ContentType=file.content_type or "application/octet-stream",
                Metadata={
                    'original-filename': file.filename,
                    'uploaded-at': datetime.utcnow().isoformat()
                }
            )
            
            is_public = folder.startswith("public/")
            file_url = f"{settings.S3_BASE_URL}/{s3_key}" if is_public else None
            
            return {
                "file_key": s3_key,
                "file_url": file_url,
                "file_size": len(file_content),
                "file_name": file.filename,
                "is_public": is_public
            }
            
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Upload failed: {str(e)}"
            )
    
    def get_presigned_url(self, file_key: str, expires_in: int = 3600) -> str:
        """Generate presigned URL for private files."""
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': file_key},
                ExpiresIn=expires_in
            )
            return url
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate URL: {str(e)}"
            )
    
    def delete_file(self, file_key: str) -> bool:
        """Delete file from S3."""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_key)
            return True
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Delete failed: {str(e)}"
            )


# Singleton
s3_service = S3Service()
