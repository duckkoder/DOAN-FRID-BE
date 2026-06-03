"""Pydantic schemas for platform APIs."""
from datetime import datetime
from typing import Any, Optional

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
    logo_url: Optional[str] = Field(None, max_length=500)

    @field_validator("school_code")
    @classmethod
    def validate_school_code(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not normalized.replace("-", "").replace("_", "").isalnum():
            raise ValueError("School code must contain only letters, numbers, hyphens, or underscores")
        return normalized


class TenantUpdateRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    logo_url: Optional[str] = Field(None, max_length=500)


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
    logo_url: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantPublicResponse(BaseModel):
    name: str
    school_code: str
    slug: str
    status: str
    logo_url: Optional[str] = None

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


class TenantMigrationRevisionInfo(BaseModel):
    revision: str
    down_revision: Optional[str] = None
    message: str
    filename: str
    created_at: datetime
    content: str


class TenantMigrationHistoryResponse(BaseModel):
    tenant_id: int
    school_code: str
    db_name: str
    current_revision: Optional[str] = None
    head_revision: Optional[str] = None
    revisions: list[TenantMigrationRevisionInfo]


class TenantMigrationDowngradeRequest(BaseModel):
    revision: str = Field(..., min_length=1, max_length=100)


class TenantMigrationUpgradeRequest(BaseModel):
    revision: str = Field(..., min_length=1, max_length=100)


class TenantDbTableInfo(BaseModel):
    table_name: str
    table_type: str
    column_count: int


class TenantDbSchemaResponse(BaseModel):
    tenant_id: int
    name: str
    school_code: str
    db_name: str
    db_host: str
    db_port: int
    alembic_version: Optional[str] = None
    has_tenant_settings: bool
    table_count: int
    tables: list[TenantDbTableInfo]


class TenantStorageCategoryUsage(BaseModel):
    category: str
    label: str
    object_count: int
    total_bytes: int


class TenantStorageUsageResponse(BaseModel):
    tenant_id: int
    name: str
    school_code: str
    storage_provider: str
    bucket: Optional[str] = None
    region: Optional[str] = None
    prefixes: list[str]
    object_count: int
    total_bytes: int
    total_mb: float
    categories: list[TenantStorageCategoryUsage]
    last_modified: Optional[datetime] = None
    scanned_at: datetime
    status: str
    message: Optional[str] = None


class TenantSecuritySessionUser(BaseModel):
    user_id: int
    full_name: str
    email: str
    role: str
    active_sessions: int
    last_session_at: Optional[datetime] = None


class TenantSecuritySummaryResponse(BaseModel):
    tenant_id: int
    name: str
    school_code: str
    status: str
    db_connected: bool
    db_message: Optional[str] = None
    current_revision: Optional[str] = None
    storage_prefix_valid: bool
    storage_prefix: str
    expected_storage_prefix: str
    gemini_key_configured: bool
    active_sessions: int
    active_admin_sessions: int
    active_users: int
    admin_users: list[TenantSecuritySessionUser]


class TenantSessionRevokeResponse(BaseModel):
    tenant_id: int
    school_code: str
    revoked_sessions: int
    message: str


class PlatformEnvConfigItem(BaseModel):
    key: str
    label: str
    group: str
    value: str | int | float | bool | None = None
    value_type: str
    description: str
    secret: bool = False
    configured: bool = True
    restart_required: bool = False


class PlatformEnvConfigResponse(BaseModel):
    items: list[PlatformEnvConfigItem]


class PlatformEnvConfigUpdateRequest(BaseModel):
    values: dict[str, str | int | float | bool | None]


class PlatformAuditLogResponse(BaseModel):
    id: int
    actor_id: Optional[int] = None
    actor_email: Optional[str] = None
    action: str
    status: str
    tenant_id: Optional[int] = None
    tenant_school_code: Optional[str] = None
    message: Optional[str] = None
    details: Optional[dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}
