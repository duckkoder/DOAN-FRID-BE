"""AI Service HTTP Client for communication with face recognition service."""
import httpx
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class FaceImageData:
    """Face image data for AI service"""
    def __init__(self, image_base64: str, step_name: str, step_number: int):
        self.image_base64 = image_base64
        self.step_name = step_name
        self.step_number = step_number
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "image_base64": self.image_base64,
            "step_name": self.step_name,
            "step_number": self.step_number
        }


class AIServiceClient:
    """Client for communicating with AI-Service."""
    
    def __init__(self):
        self.base_url = settings.AI_SERVICE_URL
        self.timeout = httpx.Timeout(30.0, connect=10.0)
        self.embedding_timeout = httpx.Timeout(300.0, connect=10.0)  # 5 minutes for embedding extraction
    
    async def create_session(
        self,
        backend_session_id: int,
        class_id: int,
        student_codes: List[str],
        ws_token: str,
        allowed_users: Optional[List[str]] = None
    ) -> Dict:
        """
        Tạo session mới trong AI-Service.
        
        Args:
            backend_session_id: ID của session trong backend DB
            class_id: ID của lớp học
            student_codes: Danh sách mã sinh viên
            ws_token: JWT token cho WebSocket authentication
            allowed_users: Danh sách user được phép (RBAC)
            
        Returns:
            Dict chứa session_id, ws_url, expires_at
            
        Raises:
            httpx.HTTPError: Nếu request thất bại
        """
        url = f"{self.base_url}/api/v1/sessions"
        callback_url = f"{settings.BACKEND_BASE_URL}/api/v1/attendance/webhook/ai-recognition"
        
        payload = {
            "backend_session_id": backend_session_id,
            "class_id": str(class_id),
            "student_codes": student_codes,
            "backend_callback_url": callback_url,
            "ws_token": ws_token,
            "allowed_users": allowed_users or []
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                
                logger.info(
                    f"AI Session created successfully",
                    extra={
                        "backend_session_id": backend_session_id,
                        "ai_session_id": data.get("session_id"),
                        "class_id": class_id,
                        "student_count": len(student_codes)
                    }
                )
                
                return data
                
        except httpx.HTTPError as e:
            logger.error(
                f"Failed to create AI session: {str(e)}",
                extra={
                    "backend_session_id": backend_session_id,
                    "class_id": class_id,
                    "error": str(e)
                }
            )
            raise
    
    async def end_session(self, ai_session_id: str) -> Dict:
        """
        Kết thúc session trong AI-Service.
        
        Args:
            ai_session_id: ID của session trong AI-Service
            
        Returns:
            Dict chứa status, statistics
            
        Raises:
            httpx.HTTPError: Nếu request thất bại
        """
        url = f"{self.base_url}/api/v1/sessions/{ai_session_id}/end"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(url)
                response.raise_for_status()
                data = response.json()
                
                logger.info(
                    f"AI Session ended successfully",
                    extra={
                        "ai_session_id": ai_session_id,
                        "statistics": data.get("statistics")
                    }
                )
                
                return data
                
        except httpx.HTTPError as e:
            logger.error(
                f"Failed to end AI session: {str(e)}",
                extra={
                    "ai_session_id": ai_session_id,
                    "error": str(e)
                }
            )
            raise
    
    async def get_session_status(self, ai_session_id: str) -> Dict:
        """
        Lấy trạng thái session từ AI-Service.
        
        Args:
            ai_session_id: ID của session trong AI-Service
            
        Returns:
            Dict chứa status, statistics
            
        Raises:
            httpx.HTTPError: Nếu request thất bại
        """
        url = f"{self.base_url}/api/v1/sessions/{ai_session_id}"
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(
                f"Failed to get AI session status: {str(e)}",
                extra={
                    "ai_session_id": ai_session_id,
                    "error": str(e)
                }
            )
            raise
    
    async def health_check(self) -> Dict:
        """
        Kiểm tra health của AI-Service.
        
        Returns:
            Dict chứa status, active_sessions, gpu info
            
        Raises:
            httpx.HTTPError: Nếu service không available
        """
        url = f"{self.base_url}/api/v1/health"
        
        try:
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.json()
                
        except httpx.HTTPError as e:
            logger.error(f"AI Service health check failed: {str(e)}")
            raise
    
    async def register_face_embeddings(
        self,
        student_code: str,
        student_id: int,
        face_images: List[FaceImageData],
        use_augmentation: bool = True,
        augmentation_count: int = 5
    ) -> Dict[str, Any]:
        """
        Send face images to AI service for embedding extraction
        
        Args:
            student_code: Student code (e.g., 'SV862155')
            student_id: Student database ID
            face_images: List of FaceImageData objects (14 images)
            use_augmentation: Whether to use data augmentation
            augmentation_count: Number of augmented images per original
            
        Returns:
            Dict containing:
                - success: bool
                - student_code: str
                - embeddings: List[Dict] with step_name, step_number, embedding
                - total_embeddings_created: int
                - processing_time_seconds: float
                
        Raises:
            httpx.HTTPError: If request fails
            Exception: For other errors
        """
        url = f"{self.base_url}/api/v1/register-face"
        
        payload = {
            "student_code": student_code,
            "student_id": student_id,
            "face_images": [img.to_dict() for img in face_images],
            "use_augmentation": use_augmentation,
            "augmentation_count": augmentation_count
        }
        
        logger.info(
            f"Sending face registration request to AI service",
            extra={
                "student_code": student_code,
                "student_id": student_id,
                "num_images": len(face_images),
                "use_augmentation": use_augmentation,
                "url": url
            }
        )
        
        try:
            async with httpx.AsyncClient(timeout=self.embedding_timeout) as client:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                
                result = response.json()
                
                logger.info(
                    f"Face registration successful",
                    extra={
                        "student_code": student_code,
                        "total_embeddings": result.get("total_embeddings_created", 0),
                        "processing_time": result.get("processing_time_seconds", 0)
                    }
                )
                
                return result
                
        except httpx.HTTPStatusError as e:
            logger.error(
                f"AI service returned error: {e.response.status_code}",
                extra={
                    "student_code": student_code,
                    "status_code": e.response.status_code,
                    "response": e.response.text
                }
            )
            raise Exception(f"AI service error: {e.response.text}")
            
        except httpx.RequestError as e:
            logger.error(
                f"Failed to connect to AI service",
                extra={
                    "student_code": student_code,
                    "error": str(e),
                    "url": url
                }
            )
            raise Exception(f"Cannot connect to AI service: {str(e)}")
            
        except Exception as e:
            logger.error(
                f"Unexpected error calling AI service",
                extra={
                    "student_code": student_code,
                    "error": str(e)
                }
            )
            raise


# Singleton instance
ai_service_client = AIServiceClient()