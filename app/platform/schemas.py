"""Pydantic schemas for platform APIs."""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class PlatformLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


class PlatformUserResponse(BaseModel):
    id: int
    full_name: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class PlatformLoginResponse(BaseModel):
    message: str = "Login successful"
    user: PlatformUserResponse
    access_token: str
    token_type: str = "bearer"


class TenantCreateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    school_code: str = Field(..., min_length=2, max_length=100)
    storage_provider: str = Field("s3", max_length=50)
    storage_region: Optional[str] = Field(None, max_length=100)

    @field_validator("school_code")
    @classmethod
    def validate_school_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("School code must contain only letters, numbers, hyphens, or underscores")
        return normalized


class TenantUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)


class TenantStorageUpdateRequest(BaseModel):
    storage_provider: Optional[str] = Field(None, max_length=50)
    storage_bucket: Optional[str] = Field(None, max_length=255)
    storage_region: Optional[str] = Field(None, max_length=100)
    storage_prefix: Optional[str] = Field(None, max_length=255)


class TenantDbConnectionUpdateRequest(BaseModel):
    """Cập nhật db_host/db_port khi tenant bị lưu sai (ví dụ: localhost → db)."""
    db_host: str = Field(..., min_length=1, max_length=255)
    db_port: int = Field(5432, ge=1, le=65535)


class TenantAdminCreateRequest(BaseModel):
    full_name: str = Field(..., min_length=2, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    phone: Optional[str] = Field(None, max_length=50)


class TenantResponse(BaseModel):
    id: int
    name: str
    school_code: str
    slug: str
    status: str
    db_name: str
    db_host: str
    db_port: int
    db_user: str
    storage_provider: str
    storage_bucket: Optional[str]
    storage_region: Optional[str]
    storage_prefix: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantPublicResponse(BaseModel):
    name: str
    school_code: str
    slug: str
    status: str

    model_config = {"from_attributes": True}


class TenantMigrationResult(BaseModel):
    tenant_id: int
    name: str
    school_code: str
    db_name: str
    status: str
    message: str


class TenantMigrationBatchResponse(BaseModel):
    total: int
    succeeded: int
    failed: int
    results: list[TenantMigrationResult]
