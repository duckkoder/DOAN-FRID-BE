"""Platform security inspection and tenant session controls."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import distinct, func, text
from sqlalchemy.orm import Session

from app.database.tenant_session import get_tenant_sessionmaker
from app.models.refresh_token import RefreshToken
from app.models.tenant_secret import TenantSecret
from app.models.user import User
from app.platform.models.platform_user import PlatformUser
from app.platform.models.tenant import Tenant
from app.platform.services.audit_log_service import PlatformAuditLogService
from app.platform.services.tenant_service import TenantService, get_tenant_or_404


class TenantSecurityService:
    """Read tenant security posture and revoke tenant refresh-token sessions."""

    @classmethod
    def list_summaries(cls, platform_db: Session) -> list[dict[str, Any]]:
        tenants = TenantService.list_tenants(platform_db)
        return [cls.inspect_tenant(tenant, platform_db) for tenant in tenants]

    @classmethod
    def inspect_tenant(cls, tenant: Tenant, platform_db: Session) -> dict[str, Any]:
        expected_prefix = f"{tenant.school_code}/"
        base = {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "school_code": tenant.school_code,
            "status": tenant.status,
            "db_connected": False,
            "db_message": None,
            "current_revision": None,
            "storage_prefix_valid": tenant.storage_prefix == expected_prefix,
            "storage_prefix": tenant.storage_prefix,
            "expected_storage_prefix": expected_prefix,
            "gemini_key_configured": False,
            "active_sessions": 0,
            "active_admin_sessions": 0,
            "active_users": 0,
            "admin_users": [],
        }

        try:
            session_factory = get_tenant_sessionmaker(tenant)
            tenant_db = session_factory()
        except Exception as exc:
            base["db_message"] = str(exc)
            return base

        try:
            base["db_connected"] = True
            base["current_revision"] = cls._current_revision(tenant_db)
            base["gemini_key_configured"] = cls._has_active_secret(tenant_db, "gemini_api_key")

            now = datetime.utcnow()
            active_query = (
                tenant_db.query(RefreshToken)
                .join(User, User.id == RefreshToken.user_id)
                .filter(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
            )
            base["active_sessions"] = active_query.count()
            base["active_users"] = (
                tenant_db.query(func.count(distinct(RefreshToken.user_id)))
                .filter(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
                .scalar()
                or 0
            )

            admin_rows = (
                tenant_db.query(
                    User.id,
                    User.full_name,
                    User.email,
                    User.role,
                    func.count(RefreshToken.id).label("active_sessions"),
                    func.max(RefreshToken.created_at).label("last_session_at"),
                )
                .join(RefreshToken, RefreshToken.user_id == User.id)
                .filter(
                    User.role == "admin",
                    RefreshToken.revoked_at.is_(None),
                    RefreshToken.expires_at > now,
                )
                .group_by(User.id, User.full_name, User.email, User.role)
                .order_by(func.max(RefreshToken.created_at).desc())
                .all()
            )
            base["admin_users"] = [
                {
                    "user_id": row.id,
                    "full_name": row.full_name,
                    "email": row.email,
                    "role": row.role,
                    "active_sessions": row.active_sessions,
                    "last_session_at": row.last_session_at,
                }
                for row in admin_rows
            ]
            base["active_admin_sessions"] = sum(item["active_sessions"] for item in base["admin_users"])
            return base
        except Exception as exc:
            base["db_connected"] = False
            base["db_message"] = str(exc)
            return base
        finally:
            tenant_db.close()

    @classmethod
    def revoke_admin_sessions(
        cls,
        tenant_id: int,
        platform_db: Session,
        actor: PlatformUser,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        tenant = get_tenant_or_404(platform_db, tenant_id)
        revoked = cls._revoke_sessions(tenant, role="admin", user_id=user_id)
        PlatformAuditLogService.record(
            platform_db,
            actor,
            "tenant.sessions.revoke_admin",
            tenant=tenant,
            message=f"Revoked {revoked} tenant admin sessions",
            details={"revoked_sessions": revoked, "user_id": user_id},
        )
        return {
            "tenant_id": tenant.id,
            "school_code": tenant.school_code,
            "revoked_sessions": revoked,
            "message": f"Revoked {revoked} admin sessions",
        }

    @classmethod
    def logout_all_users(cls, tenant_id: int, platform_db: Session, actor: PlatformUser) -> dict[str, Any]:
        tenant = get_tenant_or_404(platform_db, tenant_id)
        revoked = cls._revoke_sessions(tenant)
        PlatformAuditLogService.record(
            platform_db,
            actor,
            "tenant.sessions.logout_all",
            tenant=tenant,
            message=f"Logged out all tenant users by revoking {revoked} sessions",
            details={"revoked_sessions": revoked},
        )
        return {
            "tenant_id": tenant.id,
            "school_code": tenant.school_code,
            "revoked_sessions": revoked,
            "message": f"Revoked {revoked} sessions",
        }

    @staticmethod
    def _current_revision(db: Session) -> str | None:
        result = db.execute(text("SELECT to_regclass('public.alembic_version')")).scalar()
        if not result:
            return None
        return db.execute(text("SELECT version_num FROM public.alembic_version LIMIT 1")).scalar()

    @staticmethod
    def _has_active_secret(db: Session, key_name: str) -> bool:
        return (
            db.query(TenantSecret)
            .filter(TenantSecret.key_name == key_name, TenantSecret.status == "active")
            .first()
            is not None
        )

    @staticmethod
    def _revoke_sessions(tenant: Tenant, role: str | None = None, user_id: int | None = None) -> int:
        session_factory = get_tenant_sessionmaker(tenant)
        db = session_factory()
        try:
            now = datetime.utcnow()
            query = (
                db.query(RefreshToken)
                .join(User, User.id == RefreshToken.user_id)
                .filter(RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)
            )
            if role:
                query = query.filter(User.role == role)
            if user_id:
                query = query.filter(User.id == user_id)

            tokens = query.all()
            for token in tokens:
                token.revoked_at = now
            db.commit()
            return len(tokens)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
