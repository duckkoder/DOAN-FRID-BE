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
        folder: Literal["public/avatars", "private/documents", "private/faces", "private/attendance-evidence"],
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
        """
        Generate presigned URL for private files.
        
        Args:
            file_key: S3 key of the file
            expires_in: URL expiration time in seconds (default: 1 hour)
                       For admin review: recommend 7200 (2 hours) or more
        
        Returns:
            Presigned URL string
        """
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
    
    async def upload_base64_image(
        self,
        base64_data: str,
        folder: str,
        filename: str
    ) -> str:
        """
        Upload ảnh từ base64 string lên S3.
        
        Args:
            base64_data: Base64 encoded image (without data:image/jpeg;base64, prefix)
            folder: Folder trong S3 bucket (e.g., "private/faces")
            filename: Tên file bao gồm subfolder (e.g., "123/SV001_1705392123.jpg")
            
        Returns:
            S3 URL của file đã upload
        """
        import base64
        from io import BytesIO
        
        try:
            # Decode base64 to bytes
            image_bytes = base64.b64decode(base64_data)
            
            # Create file-like object
            file_obj = BytesIO(image_bytes)
            file_obj.seek(0)
            
            # Generate S3 key
            file_key = f"{folder}/{filename}"
            
            # Upload to S3
            self.s3_client.upload_fileobj(
                file_obj,
                self.bucket_name,
                file_key,
                ExtraArgs={
                    'ContentType': 'image/jpeg',
                    'ACL': 'private',
                    'Metadata': {
                        'uploaded_at': datetime.utcnow().isoformat(),
                        'source': 'ai_service_callback'
                    }
                }
            )
            
            # Return S3 URL
            s3_url = f"https://{self.bucket_name}.s3.{settings.AWS_REGION}.amazonaws.com/{file_key}"
            return s3_url
            
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload base64 image: {str(e)}"
            )
    
    def batch_generate_presigned_urls(
        self, 
        file_keys: list[str], 
        expires_in: int = 7200
    ) -> dict[str, str]:
        """
        Batch generate presigned URLs for multiple files.
        
        Args:
            file_keys: List of S3 keys
            expires_in: URL expiration time in seconds (default: 2 hours for admin review)
        
        Returns:
            Dict mapping file_key to presigned URL
        """
        urls = {}
        for file_key in file_keys:
            try:
                urls[file_key] = self.get_presigned_url(file_key, expires_in)
            except Exception as e:
                print(f"Failed to generate URL for {file_key}: {e}")
                urls[file_key] = None
        
        return urls
    
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
    
    def generate_face_image_path(self, student_id: int, step_name: str, step_number: int) -> str:
        """
        Generate S3 path for face registration image.
        
        Args:
            student_id: Student ID
            step_name: Verification step name
            step_number: Step number (1-14)
        
        Returns:
            S3 key path
        """
        timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
        filename = f"{step_number:02d}_{step_name}_{timestamp}.jpg"
        s3_key = f"private/faces/student_{student_id}/{filename}"
        return s3_key
    
    async def upload_face_image(
        self,
        image_data: bytes,
        student_id: int,
        step_name: str,
        step_number: int,
        metadata: dict = None
    ) -> dict:
        """
        Upload face image to S3.
        
        Args:
            image_data: Image bytes (JPEG)
            student_id: Student ID
            step_name: Verification step name
            step_number: Step number
            metadata: Additional metadata
        
        Returns:
            Dict with file_key and file_size (NO URL - generate on-demand when needed)
        """
        s3_key = self.generate_face_image_path(student_id, step_name, step_number)
        
        # Prepare metadata
        s3_metadata = {
            'student-id': str(student_id),
            'step-name': step_name,
            'step-number': str(step_number),
            'uploaded-at': datetime.utcnow().isoformat()
        }
        
        if metadata:
            for key, value in metadata.items():
                s3_metadata[f'custom-{key}'] = str(value)
        
        # Upload
        try:
            self.s3_client.put_object(
                Bucket=self.bucket_name,
                Key=s3_key,
                Body=image_data,
                ContentType="image/jpeg",
                Metadata=s3_metadata
            )
            
            # ✅ DON'T generate URL here - it will be generated on-demand when admin reviews
            # This prevents URL expiration issues
            
            return {
                "file_key": s3_key,
                "file_size": len(image_data),
                "step_name": step_name,
                "step_number": step_number,
                "is_public": False
            }
            
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Face image upload failed: {str(e)}"
            )
    
    async def batch_upload_face_images(
        self,
        images_data: list[dict],
        student_id: int
    ) -> list[dict]:
        """
        Batch upload multiple face images.
        
        Args:
            images_data: List of dicts containing:
                - image_data: bytes
                - step_name: str
                - step_number: int
                - metadata: dict (optional)
            student_id: Student ID
        
        Returns:
            List of upload results
        """
        results = []
        
        for image_info in images_data:
            try:
                result = await self.upload_face_image(
                    image_data=image_info["image_data"],
                    student_id=student_id,
                    step_name=image_info["step_name"],
                    step_number=image_info["step_number"],
                    metadata=image_info.get("metadata")
                )
                results.append({
                    "success": True,
                    "step_number": image_info["step_number"],
                    **result
                })
            except Exception as e:
                results.append({
                    "success": False,
                    "step_number": image_info["step_number"],
                    "error": str(e)
                })
        
        return results
    
    def batch_delete_files(self, file_keys: list[str]) -> dict:
        """
        Batch delete multiple files from S3.
        
        Args:
            file_keys: List of S3 keys to delete
        
        Returns:
            Dict with deleted count and errors
        """
        if not file_keys:
            return {"deleted": 0, "errors": []}
        
        try:
            # S3 batch delete (max 1000 at a time)
            objects_to_delete = [{"Key": key} for key in file_keys]
            
            response = self.s3_client.delete_objects(
                Bucket=self.bucket_name,
                Delete={"Objects": objects_to_delete}
            )
            
            deleted = response.get("Deleted", [])
            errors = response.get("Errors", [])
            
            return {
                "deleted": len(deleted),
                "errors": errors
            }
            
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Batch delete failed: {str(e)}"
            )
    
    async def download_file(self, file_key: str) -> bytes:
        """
        Download file from S3.
        
        Args:
            file_key: S3 key of the file
        
        Returns:
            File content as bytes
            
        Raises:
            HTTPException: If file not found or download fails
        """
        try:
            response = self.s3_client.get_object(
                Bucket=self.bucket_name,
                Key=file_key
            )
            
            # Read the file content
            file_content = response['Body'].read()
            
            return file_content
            
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', '')
            
            if error_code == 'NoSuchKey':
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"File not found: {file_key}"
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to download file: {str(e)}"
                )


# Singleton
s3_service = S3Service()
