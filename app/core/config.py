"""Application configuration using Pydantic Settings."""
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv
import os

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
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    ALLOWED_ORIGINS: list = ["http://localhost:3000", "http://localhost:5173"]

    # File Upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 10 * 1024 * 1024  # 10MB

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


settings = Settings()