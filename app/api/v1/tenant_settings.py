"""Tenant settings API."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.tenant_settings import (
    TenantSettingListResponse,
    TenantSettingResponse,
    TenantSettingUpsertRequest,
    TenantSecretListResponse,
    TenantSecretResponse,
    TenantSecretUpsertRequest,
)
from app.services.tenant_setting_service import TenantSettingService
from app.services.tenant_secret_service import TenantSecretService


router = APIRouter(prefix="/tenant/settings", tags=["Tenant Settings"])


@router.get("/values", response_model=TenantSettingListResponse)
async def list_tenant_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TenantSettingService.list_settings(db, current_user)


@router.put("/values/{key_name}", response_model=TenantSettingResponse)
async def upsert_tenant_setting(
    key_name: str,
    request: TenantSettingUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TenantSettingService.upsert_setting(db, current_user, key_name, request.value)


@router.get("/secrets", response_model=TenantSecretListResponse)
async def list_tenant_secrets(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TenantSecretService.list_secrets(db, current_user)


@router.put("/secrets/{key_name}", response_model=TenantSecretResponse)
async def upsert_tenant_secret(
    key_name: str,
    request: TenantSecretUpsertRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TenantSecretService.upsert_secret(db, current_user, key_name, request.value)


@router.delete("/secrets/{key_name}")
async def delete_tenant_secret(
    key_name: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return TenantSecretService.delete_secret(db, current_user, key_name)
