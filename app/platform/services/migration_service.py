"""Tenant database migration service."""
import ast
import re
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
import psycopg2
from sqlalchemy.orm import Session

from app.database.tenant_session import reset_tenant_sessionmaker
from app.platform.models.platform_user import PlatformUser
from app.platform.models.tenant import Tenant
from app.platform.schemas import (
    TenantMigrationBatchResponse,
    TenantMigrationHistoryResponse,
    TenantMigrationResult,
    TenantMigrationRevisionInfo,
)
from app.platform.services.tenant_service import get_tenant_or_404
from app.platform.services.audit_log_service import PlatformAuditLogService
from app.platform.tenant_provisioning import (
    build_tenant_database_url,
    create_tenant_database,
    ensure_tenant_extensions,
    run_tenant_downgrade,
    run_tenant_migrations,
    run_tenant_upgrade,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TENANT_MIGRATION_DIR = PROJECT_ROOT / "alembic" / "versions"
REVISION_RE = re.compile(r"^revision\s*:\s*str\s*=\s*['\"]([^'\"]+)['\"]|^revision\s*=\s*['\"]([^'\"]+)['\"]", re.M)
DOWN_REVISION_RE = re.compile(
    r"^down_revision\s*:\s*[^=]+=\s*(.+)$|^down_revision\s*=\s*(.+)$",
    re.M,
)


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


def _extract_revision_from_file(path: Path) -> tuple[str | None, str | None, str]:
    content = path.read_text(encoding="utf-8")
    revision_match = REVISION_RE.search(content)
    revision = next((g for g in revision_match.groups() if g), None) if revision_match else None

    down_match = DOWN_REVISION_RE.search(content)
    down_revision = None
    if down_match:
        raw_down_revision = next((g for g in down_match.groups() if g), "None").strip()
        try:
            parsed = ast.literal_eval(raw_down_revision)
            if isinstance(parsed, str):
                down_revision = parsed
            elif isinstance(parsed, (list, tuple)) and parsed:
                down_revision = ",".join(str(item) for item in parsed)
        except Exception:
            down_revision = raw_down_revision.strip("'\"") if raw_down_revision != "None" else None

    message = path.stem.split("-", 1)[1].replace("_", " ") if "-" in path.stem else path.stem
    return revision, down_revision, message


def _list_revision_files() -> list[TenantMigrationRevisionInfo]:
    revisions: list[TenantMigrationRevisionInfo] = []
    for path in sorted(TENANT_MIGRATION_DIR.glob("*.py"), key=lambda p: p.stat().st_mtime, reverse=True):
        if path.name == "__init__.py":
            continue
        content = path.read_text(encoding="utf-8")
        revision, down_revision, message = _extract_revision_from_file(path)
        if not revision:
            continue
        revisions.append(TenantMigrationRevisionInfo(
            revision=revision,
            down_revision=down_revision,
            message=message,
            filename=path.name,
            created_at=datetime.fromtimestamp(path.stat().st_mtime),
            content=content,
        ))
    return revisions


def _find_head_revision(revisions: list[TenantMigrationRevisionInfo]) -> str | None:
    revision_ids = {item.revision for item in revisions}
    parent_ids: set[str] = set()
    for item in revisions:
        if not item.down_revision:
            continue
        parent_ids.update(part.strip() for part in item.down_revision.split(",") if part.strip())
    heads = sorted(revision_ids - parent_ids)
    return heads[0] if heads else (revisions[0].revision if revisions else None)


def _read_current_revision(tenant: Tenant) -> str | None:
    url = build_tenant_database_url(tenant)
    conn = psycopg2.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.alembic_version')")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("SELECT version_num FROM public.alembic_version LIMIT 1")
            row = cur.fetchone()
            return row[0] if row else None
    finally:
        conn.close()


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
    def migrate_one_with_audit(tenant_id: int, db: Session, actor: PlatformUser) -> TenantMigrationResult:
        tenant = get_tenant_or_404(db, tenant_id)
        before = MigrationService.history(tenant_id, db)
        try:
            result = MigrationService.migrate_one(tenant_id, db)
            after = MigrationService.history(tenant_id, db)
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration",
                tenant=tenant,
                message=result.message,
                details={
                    "db_name": result.db_name,
                    "from_revision": before.current_revision,
                    "to_revision": after.current_revision,
                    "head_revision": after.head_revision,
                },
            )
            return result
        except Exception as exc:
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration",
                status="failed",
                tenant=tenant,
                message=str(getattr(exc, "detail", None) or exc),
                details={
                    "db_name": tenant.db_name,
                    "from_revision": before.current_revision,
                    "head_revision": before.head_revision,
                },
            )
            raise

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

    @staticmethod
    def migrate_all_with_audit(db: Session, actor: PlatformUser) -> TenantMigrationBatchResponse:
        result = MigrationService.migrate_all(db)
        PlatformAuditLogService.record(
            db,
            actor,
            "tenant.migration_all",
            status="success" if result.failed == 0 else "partial",
            message=f"Migrated {result.succeeded}/{result.total} tenants",
            details={
                "total": result.total,
                "succeeded": result.succeeded,
                "failed": result.failed,
                "results": [item.model_dump() for item in result.results],
            },
        )
        return result

    @staticmethod
    def history(tenant_id: int, db: Session) -> TenantMigrationHistoryResponse:
        tenant = get_tenant_or_404(db, tenant_id)
        revisions = _list_revision_files()
        return TenantMigrationHistoryResponse(
            tenant_id=tenant.id,
            school_code=tenant.school_code,
            db_name=tenant.db_name,
            current_revision=_read_current_revision(tenant),
            head_revision=_find_head_revision(revisions),
            revisions=revisions,
        )

    @staticmethod
    def downgrade_one(tenant_id: int, revision: str, db: Session) -> TenantMigrationResult:
        tenant = get_tenant_or_404(db, tenant_id)
        try:
            run_tenant_downgrade(tenant, revision)
            return TenantMigrationResult(
                tenant_id=tenant.id,
                name=tenant.name,
                school_code=tenant.school_code,
                db_name=tenant.db_name,
                status="success",
                message=f"Đã downgrade về revision {revision}",
            )
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(detail),
            ) from exc

    @staticmethod
    def downgrade_one_with_audit(
        tenant_id: int,
        revision: str,
        db: Session,
        actor: PlatformUser,
    ) -> TenantMigrationResult:
        tenant = get_tenant_or_404(db, tenant_id)
        before = MigrationService.history(tenant_id, db)
        try:
            result = MigrationService.downgrade_one(tenant_id, revision, db)
            after = MigrationService.history(tenant_id, db)
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration_downgrade",
                tenant=tenant,
                message=result.message,
                details={
                    "db_name": tenant.db_name,
                    "from_revision": before.current_revision,
                    "to_revision": after.current_revision,
                    "target_revision": revision,
                },
            )
            return result
        except Exception as exc:
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration_downgrade",
                status="failed",
                tenant=tenant,
                message=str(getattr(exc, "detail", None) or exc),
                details={
                    "db_name": tenant.db_name,
                    "from_revision": before.current_revision,
                    "target_revision": revision,
                },
            )
            raise

    @staticmethod
    def upgrade_one(tenant_id: int, revision: str, db: Session) -> TenantMigrationResult:
        tenant = get_tenant_or_404(db, tenant_id)
        try:
            create_tenant_database(tenant)
            reset_tenant_sessionmaker(tenant.id)
            ensure_tenant_extensions(tenant)
            run_tenant_upgrade(tenant, revision)
            return TenantMigrationResult(
                tenant_id=tenant.id,
                name=tenant.name,
                school_code=tenant.school_code,
                db_name=tenant.db_name,
                status="success",
                message=f"Đã upgrade lên revision {revision}",
            )
        except Exception as exc:
            detail = getattr(exc, "detail", None) or str(exc)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=str(detail),
            ) from exc

    @staticmethod
    def upgrade_one_with_audit(
        tenant_id: int,
        revision: str,
        db: Session,
        actor: PlatformUser,
    ) -> TenantMigrationResult:
        tenant = get_tenant_or_404(db, tenant_id)
        before = MigrationService.history(tenant_id, db)
        try:
            result = MigrationService.upgrade_one(tenant_id, revision, db)
            after = MigrationService.history(tenant_id, db)
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration_upgrade",
                tenant=tenant,
                message=result.message,
                details={
                    "db_name": tenant.db_name,
                    "from_revision": before.current_revision,
                    "to_revision": after.current_revision,
                    "target_revision": revision,
                },
            )
            return result
        except Exception as exc:
            PlatformAuditLogService.record(
                db,
                actor,
                "tenant.migration_upgrade",
                status="failed",
                tenant=tenant,
                message=str(getattr(exc, "detail", None) or exc),
                details={
                    "db_name": tenant.db_name,
                    "from_revision": before.current_revision,
                    "target_revision": revision,
                },
            )
            raise
