"""AI Service HTTP Client for communication with face recognition service."""
import httpx
import logging
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from app.core.config import settings

logger = logging.getLogger(__name__)


class AIServiceClient:
    """Client for communicating with AI-Service."""
    
    def __init__(self):
        self.base_url = settings.AI_SERVICE_URL
        self.timeout = httpx.Timeout(30.0, connect=10.0)
    
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


# Singleton instance
ai_service_client = AIServiceClient()
