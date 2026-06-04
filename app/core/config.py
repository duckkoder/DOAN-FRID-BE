"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os
from typing import Optional

# ✅ Force load .env file
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
env_path = os.path.join(project_root, '.env')
load_dotenv(env_path, override=True)


class Settings(BaseSettings):
    """Application settings."""

    # Project Info
    PROJECT_NAME: str = "AI Attendance System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    PLATFORM_DATABASE_URL: str = Field(
        default="postgresql://username:password@localhost:5432/platform_attandance_db",
        description="PostgreSQL database URL for SaaS platform metadata",
    )
    TENANT_DB_HOST: str = Field(
        default="localhost",
        description="PostgreSQL host stored for newly created tenant databases",
    )
    TENANT_DB_PORT: int = Field(
        default=5432,
        description="PostgreSQL port stored for newly created tenant databases",
    )
    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    SECRET_ENCRYPTION_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 120
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB
    
    # AWS S3
    AWS_ACCESS_KEY_ID: str
    AWS_SECRET_ACCESS_KEY: str
    AWS_REGION: str = "ap-southeast-1"
    AWS_S3_BUCKET_NAME: str
    S3_PUBLIC_FOLDER: str = "public"
    S3_PRIVATE_FOLDER: str = "private"
    S3_TEMP_FOLDER: str = "temp"
    PLATFORM_STORAGE_PREFIX: str = "platform/"
    TENANT_STORAGE_FOLDERS: str = "avatar,face_registration,attendance_faces,documents,leave_evidence,temp"
    
    # File limits
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: str = "jpg,jpeg,png,gif,webp"
    ALLOWED_DOCUMENT_EXTENSIONS: str = "pdf,doc,docx,xls,xlsx,jpg,jpeg,png,gif,webp"
    
    # AI Service
    AI_SERVICE_URL: str = "http://localhost:8096"  # URL của AI Service (internal)
    AI_SERVICE_PUBLIC_URL: Optional[str] = None     # URL của AI Service (public for WebSocket)
    BACKEND_BASE_URL: str = Field(
        default="http://localhost:8000",  # Default value nếu không có trong .env
        description="URL của Backend (for AI-Service callback)"
    )
    AI_SERVICE_SECRET: str = "shared-secret-key-for-hmac-verification"  # Secret key for HMAC
    AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES: int = 120  # WebSocket token expiry
    ATTENDANCE_ALLOW_CREATE_ANYTIME: bool = False
    ATTENDANCE_CREATE_WINDOW_GRACE_MINUTES: int = 0
    
    # ✅ AI Confidence Threshold cho teacher confirmation
    AI_CONFIDENCE_THRESHOLD: float = Field(
        default=0.7,
        description="Ngưỡng confidence để tự động xác nhận điểm danh. "
                    "Nếu avg_confidence >= threshold: tự động PRESENT. "
                    "Nếu < threshold: PENDING (cần giáo viên xác nhận)."
    )
    
    # Face Verification Settings
    FACE_VERIFICATION_FPS: int = 10  # Process 10 frames per second
    FACE_VERIFICATION_JPEG_QUALITY: int = 80  # JPEG compression quality (70-90)
    FACE_VERIFICATION_TIMEOUT: int = 300  # 5 minutes timeout per session
    FACE_VERIFICATION_MIN_FACE_WIDTH: int = 200  # Minimum face width in pixels
    FACE_VERIFICATION_FRAME_WIDTH: int = 640  # Frame width for processing
    FACE_VERIFICATION_FRAME_HEIGHT: int = 480  # Frame height for processing
    
    @property
    def MAX_FILE_SIZE_BYTES(self) -> int:
        return self.MAX_FILE_SIZE_MB * 1024 * 1024
    
    @property
    def S3_BASE_URL(self) -> str:
        return f"https://{self.AWS_S3_BUCKET_NAME}.s3.{self.AWS_REGION}.amazonaws.com"
    
    @property
    def ALLOWED_IMAGE_EXTENSIONS_LIST(self) -> list:
        return self.ALLOWED_IMAGE_EXTENSIONS.split(',')
    
    @property
    def ALLOWED_DOCUMENT_EXTENSIONS_LIST(self) -> list:
        return self.ALLOWED_DOCUMENT_EXTENSIONS.split(',')

    @property
    def TENANT_STORAGE_FOLDERS_LIST(self) -> list[str]:
        return [folder.strip().strip("/") for folder in self.TENANT_STORAGE_FOLDERS.split(",") if folder.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()
