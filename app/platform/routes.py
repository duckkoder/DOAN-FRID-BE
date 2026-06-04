"""Platform API routes."""
import logging
from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import StreamingResponse
from botocore.exceptions import ClientError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.platform.database import get_platform_db
from app.platform.models.platform_user import PlatformUser
from app.platform.schemas import (
    PlatformAuditLogResponse,
    PlatformEnvConfigResponse,
    PlatformEnvConfigUpdateRequest,
    PlatformLoginRequest,
    PlatformLoginResponse,
    TenantAdminCreateRequest,
    TenantCreateRequest,
    TenantDbConnectionUpdateRequest,
    TenantDbSchemaResponse,
    TenantMigrationDowngradeRequest,
    TenantMigrationBatchResponse,
    TenantMigrationHistoryResponse,
    TenantMigrationResult,
    TenantMigrationUpgradeRequest,
    TenantPublicResponse,
    TenantResponse,
    TenantSecuritySummaryResponse,
    TenantSessionRevokeResponse,
    TenantStorageUsageResponse,
    TenantStorageUpdateRequest,
    TenantUpdateRequest,
)
from app.platform.security import get_current_platform_user
from app.storage.s3_client import create_s3_client
from app.platform.services import (
    MigrationService,
    PlatformAuditLogService,
    PlatformAuthService,
    PlatformEnvConfigService,
    TenantAdminService,
    TenantDbSchemaService,
    TenantSecurityService,
    TenantService,
    TenantStorageUsageService,
)
from app.platform.services.tenant_service import get_effective_storage_bucket

router = APIRouter(prefix="/platform", tags=["Platform"])
logger = logging.getLogger(__name__)


def _tenant_logo_url(slug: str) -> str:
    return f"{settings.BACKEND_BASE_URL.rstrip('/')}{settings.API_V1_STR}/platform/public/tenants/{slug}/logo"


def _validate_logo_file(file: UploadFile) -> str:
    extension = (file.filename or "").split(".")[-1].lower()
    if extension not in settings.ALLOWED_IMAGE_EXTENSIONS_LIST:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Logo chỉ nhận ảnh: {', '.join(settings.ALLOWED_IMAGE_EXTENSIONS_LIST)}",
        )
    file.file.seek(0, 2)
    size = file.file.tell()
    file.file.seek(0)
    if size > settings.MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Logo vượt quá {settings.MAX_FILE_SIZE_MB}MB",
        )
    return extension


@router.post("/auth/login", response_model=PlatformLoginResponse)
async def platform_login(
    request: PlatformLoginRequest,
    db: Session = Depends(get_platform_db),
):
    return PlatformAuthService.login(request.email, request.password, db)


@router.get("/public/tenants/{slug}", response_model=TenantPublicResponse)
async def get_public_tenant(
    slug: str,
    db: Session = Depends(get_platform_db),
):
    return TenantService.get_public_tenant(slug, db)


@router.get("/public/tenants/{slug}/logo")
async def get_public_tenant_logo(
    slug: str,
    db: Session = Depends(get_platform_db),
):
    tenant = TenantService.get_public_tenant(slug, db)
    if not tenant.logo_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant logo not found")

    bucket = get_effective_storage_bucket(tenant)
    try:
        obj = create_s3_client().get_object(Bucket=bucket, Key=tenant.logo_key)
    except ClientError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant logo not found") from exc

    return StreamingResponse(
        obj["Body"],
        media_type=obj.get("ContentType") or "image/png",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/public/tenants", response_model=list[TenantPublicResponse])
async def list_public_tenants(
    db: Session = Depends(get_platform_db),
):
    return TenantService.list_public_tenants(db)


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantService.list_tenants(db)


@router.get("/audit-logs", response_model=list[PlatformAuditLogResponse])
async def list_audit_logs(
    limit: int = 100,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return PlatformAuditLogService.list_logs(db, limit)


@router.get("/env/ai-model", response_model=PlatformEnvConfigResponse)
async def get_ai_model_env_config(
    _: PlatformUser = Depends(get_current_platform_user),
):
    return PlatformEnvConfigService.list_items()


@router.put("/env/ai-model", response_model=PlatformEnvConfigResponse)
async def update_ai_model_env_config(
    request: PlatformEnvConfigUpdateRequest,
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return PlatformEnvConfigService.update_items(request.values, current_user)


@router.get("/env/security", response_model=PlatformEnvConfigResponse)
async def get_security_env_config(
    _: PlatformUser = Depends(get_current_platform_user),
):
    return PlatformEnvConfigService.list_security_items()


@router.put("/env/security", response_model=PlatformEnvConfigResponse)
async def update_security_env_config(
    request: PlatformEnvConfigUpdateRequest,
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return PlatformEnvConfigService.update_security_items(request.values, current_user)


@router.get("/storage/usage", response_model=list[TenantStorageUsageResponse])
async def list_storage_usage(
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantStorageUsageService.inspect_all(db)


@router.get("/tenants/{tenant_id}/storage/usage", response_model=TenantStorageUsageResponse)
async def inspect_tenant_storage_usage(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantStorageUsageService.inspect_tenant(tenant_id, db)


@router.get("/security/tenants", response_model=list[TenantSecuritySummaryResponse])
async def list_tenant_security_summaries(
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantSecurityService.list_summaries(db)


@router.post("/tenants/{tenant_id}/sessions/revoke-admin", response_model=TenantSessionRevokeResponse)
async def revoke_tenant_admin_sessions(
    tenant_id: int,
    user_id: int | None = None,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return TenantSecurityService.revoke_admin_sessions(tenant_id, db, current_user, user_id=user_id)


@router.post("/tenants/{tenant_id}/sessions/logout-all", response_model=TenantSessionRevokeResponse)
async def logout_all_tenant_users(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return TenantSecurityService.logout_all_users(tenant_id, db, current_user)


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    try:
        tenant = TenantService.create_tenant(request, db)
        PlatformAuditLogService.record(
            db,
            current_user,
            "tenant.create",
            tenant=tenant,
            message=f"Created tenant {tenant.school_code}",
            details={"db_name": tenant.db_name, "db_user": tenant.db_user},
        )
        return tenant
    except Exception as exc:
        PlatformAuditLogService.record(
            db,
            current_user,
            "tenant.create",
            status="failed",
            message=str(getattr(exc, "detail", None) or exc),
            details={"school_code": request.school_code, "name": request.name},
        )
        raise


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantService.get_tenant(tenant_id, db)


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    request: TenantUpdateRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.update_tenant(tenant_id, request, db)
    PlatformAuditLogService.record(
        db,
        current_user,
        "tenant.update_name",
        tenant=tenant,
        message=f"Updated tenant name to {tenant.name}",
    )
    return tenant


@router.post("/tenants/{tenant_id}/logo", response_model=TenantResponse)
async def upload_tenant_logo(
    tenant_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.get_tenant(tenant_id, db)
    extension = _validate_logo_file(file)
    content = await file.read()
    logo_key = f"{tenant.school_code}/logo/{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}.{extension}"
    bucket = get_effective_storage_bucket(tenant)

    try:
        create_s3_client().put_object(
            Bucket=bucket,
            Key=logo_key,
            Body=content,
            ContentType=file.content_type or "image/png",
        )
    except ClientError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Upload logo thất bại: {exc}",
        ) from exc

    tenant.logo_key = logo_key
    tenant.logo_url = _tenant_logo_url(tenant.slug)
    db.commit()
    db.refresh(tenant)

    PlatformAuditLogService.record(
        db,
        current_user,
        "tenant.update_logo",
        tenant=tenant,
        message=f"Updated tenant logo for {tenant.school_code}",
        details={"logo_key": logo_key},
    )
    return tenant


@router.patch("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.suspend_tenant(tenant_id, db)
    PlatformAuditLogService.record(db, current_user, "tenant.suspend", tenant=tenant, message="Suspended tenant")
    return tenant


@router.patch("/tenants/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.activate_tenant(tenant_id, db)
    PlatformAuditLogService.record(db, current_user, "tenant.activate", tenant=tenant, message="Activated tenant")
    return tenant


@router.patch("/tenants/{tenant_id}/storage", response_model=TenantResponse)
async def update_tenant_storage(
    tenant_id: int,
    request: TenantStorageUpdateRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    fields = request.model_dump(exclude_unset=True)
    tenant = TenantService.update_storage(tenant_id, fields, db)
    PlatformAuditLogService.record(
        db,
        current_user,
        "tenant.update_storage",
        tenant=tenant,
        message="Updated tenant storage config",
        details={"fields": list(fields.keys())},
    )
    return tenant


@router.patch("/tenants/{tenant_id}/db-connection", response_model=TenantResponse)
async def update_tenant_db_connection(
    tenant_id: int,
    request: TenantDbConnectionUpdateRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.update_db_connection(tenant_id, request.db_host, request.db_port, db)
    PlatformAuditLogService.record(
        db,
        current_user,
        "tenant.update_db_connection",
        tenant=tenant,
        message="Updated tenant database connection",
        details={"db_host": tenant.db_host, "db_port": tenant.db_port},
    )
    return tenant


@router.post("/tenants/{tenant_id}/migrations", response_model=TenantMigrationResult)
async def migrate_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return MigrationService.migrate_one_with_audit(tenant_id, db, current_user)


@router.get("/tenants/{tenant_id}/migrations", response_model=TenantMigrationHistoryResponse)
async def get_tenant_migration_history(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return MigrationService.history(tenant_id, db)


@router.post("/tenants/{tenant_id}/migrations/downgrade", response_model=TenantMigrationResult)
async def downgrade_tenant_migration(
    tenant_id: int,
    request: TenantMigrationDowngradeRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return MigrationService.downgrade_one_with_audit(tenant_id, request.revision, db, current_user)


@router.post("/tenants/{tenant_id}/migrations/upgrade", response_model=TenantMigrationResult)
async def upgrade_tenant_migration(
    tenant_id: int,
    request: TenantMigrationUpgradeRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return MigrationService.upgrade_one_with_audit(tenant_id, request.revision, db, current_user)


@router.post("/migrations/tenants", response_model=TenantMigrationBatchResponse)
async def migrate_all_tenants(
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    return MigrationService.migrate_all_with_audit(db, current_user)


@router.get("/tenants/{tenant_id}/db-schema", response_model=TenantDbSchemaResponse)
async def inspect_tenant_db_schema(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    return TenantDbSchemaService.inspect_tenant(tenant_id, db)


@router.post("/tenants/{tenant_id}/admin", status_code=status.HTTP_201_CREATED)
async def create_tenant_admin(
    tenant_id: int,
    request: TenantAdminCreateRequest,
    db: Session = Depends(get_platform_db),
    current_user: PlatformUser = Depends(get_current_platform_user),
):
    tenant = TenantService.get_tenant(tenant_id, db)
    try:
        admin = TenantAdminService.create_admin(tenant_id, request, db)
        PlatformAuditLogService.record(
            db,
            current_user,
            "tenant.admin_create",
            tenant=tenant,
            message=f"Created tenant admin {admin['email']}",
            details={"admin_email": admin["email"]},
        )
        return admin
    except Exception as exc:
        PlatformAuditLogService.record(
            db,
            current_user,
            "tenant.admin_create",
            status="failed",
            tenant=tenant,
            message=str(getattr(exc, "detail", None) or exc),
            details={"admin_email": request.email},
        )
        raise
