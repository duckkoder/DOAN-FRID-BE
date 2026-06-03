"""Platform audit log service."""
import logging
from typing import Any

from sqlalchemy.orm import Session

from app.platform.models.platform_audit_log import PlatformAuditLog
from app.platform.models.platform_user import PlatformUser
from app.platform.models.tenant import Tenant

logger = logging.getLogger(__name__)


class PlatformAuditLogService:
    """Write and read operational logs for super admin actions."""

    @staticmethod
    def record(
        db: Session,
        actor: PlatformUser | None,
        action: str,
        status: str = "success",
        tenant: Tenant | None = None,
        message: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        try:
            db.add(PlatformAuditLog(
                actor_id=actor.id if actor else None,
                actor_email=actor.email if actor else None,
                action=action,
                status=status,
                tenant_id=tenant.id if tenant else None,
                tenant_school_code=tenant.school_code if tenant else None,
                message=message,
                details=details,
            ))
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("platform.audit_log.write_failed action=%s status=%s", action, status)

    @staticmethod
    def list_logs(db: Session, limit: int = 100) -> list[PlatformAuditLog]:
        safe_limit = max(1, min(limit, 500))
        return (
            db.query(PlatformAuditLog)
            .order_by(PlatformAuditLog.created_at.desc(), PlatformAuditLog.id.desc())
            .limit(safe_limit)
            .all()
        )
