"""Tenant database migration service."""

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.database.tenant_session import reset_tenant_sessionmaker
from app.platform.models.tenant import Tenant
from app.platform.schemas import TenantMigrationBatchResponse, TenantMigrationResult
from app.platform.services.tenant_service import get_tenant_or_404
from app.platform.tenant_provisioning import create_tenant_database, ensure_tenant_extensions, run_tenant_migrations


def _run_migration_for_tenant(tenant: Tenant) -> TenantMigrationResult:
    """Chạy migration cho một tenant, trả về kết quả dù thành công hay thất bại."""
    try:
        create_tenant_database(tenant)
        reset_tenant_sessionmaker(tenant.id)
        ensure_tenant_extensions(tenant)
        run_tenant_migrations(tenant)
        return TenantMigrationResult(
            tenant_id=tenant.id,
            name=tenant.name,
            school_code=tenant.school_code,
            db_name=tenant.db_name,
            status="success",
            message="Đã migrate lên revision mới nhất",
        )
    except Exception as exc:
        detail = getattr(exc, "detail", None) or str(exc)
        return TenantMigrationResult(
            tenant_id=tenant.id,
            name=tenant.name,
            school_code=tenant.school_code,
            db_name=tenant.db_name,
            status="failed",
            message=str(detail),
        )


class MigrationService:

    @staticmethod
    def migrate_one(tenant_id: int, db: Session) -> TenantMigrationResult:
        """Chạy Alembic upgrade head cho một tenant database."""
        tenant = get_tenant_or_404(db, tenant_id)
        result = _run_migration_for_tenant(tenant)
        if result.status == "failed":
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.message,
            )
        return result

    @staticmethod
    def migrate_all(db: Session) -> TenantMigrationBatchResponse:
        """Chạy Alembic upgrade head cho tất cả tenant. Tenant lỗi không dừng batch."""
        tenants = db.query(Tenant).order_by(Tenant.id.asc()).all()
        results = [_run_migration_for_tenant(t) for t in tenants]
        succeeded = sum(1 for r in results if r.status == "success")
        return TenantMigrationBatchResponse(
            total=len(results),
            succeeded=succeeded,
            failed=len(results) - succeeded,
            results=results,
        )
