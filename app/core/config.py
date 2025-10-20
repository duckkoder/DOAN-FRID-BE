"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os
from typing import Optional

# ✅ Force load .env file
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path, override=True)


class Settings(BaseSettings):
    """Application settings."""

    # Project Info
    PROJECT_NAME: str = "AI Attendance System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"

    # Database - ✅ Không có default value, bắt buộc phải có trong .env
    DATABASE_URL: str = Field(..., description="PostgreSQL database URL")

    # Security
    SECRET_KEY: str = "your-secret-key-here-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 300
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
    
    # File limits
    MAX_FILE_SIZE_MB: int = 10
    ALLOWED_IMAGE_EXTENSIONS: str = "jpg,jpeg,png,gif,webp"
    ALLOWED_DOCUMENT_EXTENSIONS: str = "pdf,doc,docx,xls,xlsx,jpg,jpeg,png,gif,webp"
    
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

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()