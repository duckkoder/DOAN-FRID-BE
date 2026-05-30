"""Platform API routes — thin endpoints, business logic nằm trong services.py."""
import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.platform.database import get_platform_db
from app.platform.models.platform_user import PlatformUser
from app.platform.schemas import (
    PlatformLoginRequest,
    PlatformLoginResponse,
    TenantAdminCreateRequest,
    TenantCreateRequest,
    TenantDbConnectionUpdateRequest,
    TenantMigrationBatchResponse,
    TenantMigrationResult,
    TenantPublicResponse,
    TenantResponse,
    TenantStorageUpdateRequest,
    TenantUpdateRequest,
)
from app.platform.security import get_current_platform_user
from app.platform.services import (
    MigrationService,
    PlatformAuthService,
    TenantAdminService,
    TenantService,
)

router = APIRouter(prefix="/platform", tags=["Platform"])
logger = logging.getLogger(__name__)


# ─── AUTH ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=PlatformLoginResponse)
async def platform_login(
    request: PlatformLoginRequest,
    db: Session = Depends(get_platform_db),
):
    """Đăng nhập super admin — trả về platform-scoped JWT."""
    return PlatformAuthService.login(request.email, request.password, db)


# ─── TENANT CRUD ────────────────────────────────────────────────────────────────

@router.get("/public/tenants/{slug}", response_model=TenantPublicResponse)
async def get_public_tenant(
    slug: str,
    db: Session = Depends(get_platform_db),
):
    """Public tenant metadata for tenant login page. No auth required."""
    return TenantService.get_public_tenant(slug, db)


@router.get("/public/tenants", response_model=list[TenantPublicResponse])
async def list_public_tenants(
    db: Session = Depends(get_platform_db),
):
    """Public active tenant list for homepage partner selector. No auth required."""
    return TenantService.list_public_tenants(db)


@router.get("/tenants", response_model=list[TenantResponse])
async def list_tenants(
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Lấy danh sách tất cả tenant."""
    return TenantService.list_tenants(db)


@router.post("/tenants", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(
    request: TenantCreateRequest,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Tạo tenant mới: tạo DB → chạy migration → lưu vào platform DB."""
    return TenantService.create_tenant(request, db)


@router.get("/tenants/{tenant_id}", response_model=TenantResponse)
async def get_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Lấy thông tin chi tiết một tenant."""
    return TenantService.get_tenant(tenant_id, db)


@router.patch("/tenants/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: int,
    request: TenantUpdateRequest,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Update tenant display name. School code/slug/db identifiers are immutable."""
    return TenantService.update_tenant(tenant_id, request, db)


# ─── TENANT STATUS ──────────────────────────────────────────────────────────────

@router.patch("/tenants/{tenant_id}/suspend", response_model=TenantResponse)
async def suspend_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Tạm khóa tenant — chặn đăng nhập của toàn bộ user thuộc tenant đó."""
    return TenantService.suspend_tenant(tenant_id, db)


@router.patch("/tenants/{tenant_id}/activate", response_model=TenantResponse)
async def activate_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Kích hoạt lại tenant đang bị tạm khóa."""
    return TenantService.activate_tenant(tenant_id, db)


# ─── TENANT STORAGE ─────────────────────────────────────────────────────────────

@router.patch("/tenants/{tenant_id}/storage", response_model=TenantResponse)
async def update_tenant_storage(
    tenant_id: int,
    request: TenantStorageUpdateRequest,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Cập nhật cấu hình storage (provider/bucket/region/prefix) của tenant."""
    return TenantService.update_storage(
        tenant_id,
        request.model_dump(exclude_unset=True),
        db,
    )


@router.patch("/tenants/{tenant_id}/db-connection", response_model=TenantResponse)
async def update_tenant_db_connection(
    tenant_id: int,
    request: TenantDbConnectionUpdateRequest,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """
    Sửa db_host/db_port của tenant.
    Dùng khi tenant được tạo với host sai (ví dụ: localhost thay vì tên service Docker).
    Đồng thời xóa cached engine để buộc reconnect với thông tin mới.
    """
    return TenantService.update_db_connection(
        tenant_id,
        request.db_host,
        request.db_port,
        db,
    )


# ─── MIGRATIONS ─────────────────────────────────────────────────────────────────

@router.post("/tenants/{tenant_id}/migrations", response_model=TenantMigrationResult)
async def migrate_tenant(
    tenant_id: int,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Chạy Alembic upgrade head cho một tenant database."""
    return MigrationService.migrate_one(tenant_id, db)


@router.post("/migrations/tenants", response_model=TenantMigrationBatchResponse)
async def migrate_all_tenants(
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Chạy Alembic upgrade head cho toàn bộ tenant. Tenant lỗi không dừng batch."""
    return MigrationService.migrate_all(db)


# ─── TENANT ADMIN ───────────────────────────────────────────────────────────────

@router.post("/tenants/{tenant_id}/admin", status_code=status.HTTP_201_CREATED)
async def create_tenant_admin(
    tenant_id: int,
    request: TenantAdminCreateRequest,
    db: Session = Depends(get_platform_db),
    _: PlatformUser = Depends(get_current_platform_user),
):
    """Tạo tài khoản admin bên trong database của tenant chỉ định."""
    return TenantAdminService.create_admin(tenant_id, request, db)
