"""Schemas for tenant settings APIs."""
from datetime import datetime

from pydantic import BaseModel, Field


class TenantSecretUpsertRequest(BaseModel):
    value: str = Field(..., min_length=1, max_length=10000)


class TenantSecretResponse(BaseModel):
    key_name: str
    configured: bool
    status: str
    updated_at: datetime


class TenantSecretListResponse(BaseModel):
    secrets: list[TenantSecretResponse]


class TenantSettingUpsertRequest(BaseModel):
    value: str = Field(..., min_length=1, max_length=1000)


class TenantSettingResponse(BaseModel):
    key_name: str
    value: str
    updated_at: datetime | None = None


class TenantSettingListResponse(BaseModel):
    settings: list[TenantSettingResponse]
