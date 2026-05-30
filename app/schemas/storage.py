"""Schemas for tenant storage APIs."""
from pydantic import BaseModel, Field


class PresignedUploadRequest(BaseModel):
    folder: str = Field(..., min_length=1, max_length=200)
    filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field("application/octet-stream", max_length=255)


class PresignedUploadResponse(BaseModel):
    upload_url: str
    bucket: str
    key: str
    expires_in: int


class PresignedDownloadResponse(BaseModel):
    download_url: str
    bucket: str
    key: str
    expires_in: int

