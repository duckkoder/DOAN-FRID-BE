"""Tenant admin account creation service."""
import logging

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.database.tenant_session import get_tenant_sessionmaker, reset_tenant_sessionmaker
from app.models.admin import Admin
from app.models.user import User
from app.platform.schemas import TenantAdminCreateRequest
from app.platform.services.tenant_service import get_tenant_or_404
from app.platform.tenant_provisioning import create_tenant_database

logger = logging.getLogger(__name__)


class TenantAdminService:

    @staticmethod
    def create_admin(tenant_id: int, request: TenantAdminCreateRequest, db: Session) -> dict:
        """
        Tạo tài khoản admin bên trong database của tenant.
        Kết nối trực tiếp vào tenant DB — không dùng platform DB.
        """
        tenant = get_tenant_or_404(db, tenant_id)
        if tenant.status != "active":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tenant đang bị tạm khóa, không thể tạo admin",
            )

        create_tenant_database(tenant)
        reset_tenant_sessionmaker(tenant.id)
        tenant_db = get_tenant_sessionmaker(tenant)()
        try:
            existing = tenant_db.query(User).filter(User.email == request.email).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Email '{request.email}' đã tồn tại trong tenant này",
                )

            user = User(
                full_name=request.full_name,
                email=request.email,
                password_hash=get_password_hash(request.password),
                role="admin",
                phone=request.phone,
                is_active=True,
            )
            tenant_db.add(user)
            tenant_db.flush()
            tenant_db.add(Admin(user_id=user.id))
            tenant_db.commit()
            tenant_db.refresh(user)

            return {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "role": user.role,
                "is_active": user.is_active,
            }
        except HTTPException:
            tenant_db.rollback()
            raise
        except Exception as exc:
            tenant_db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tạo admin thất bại: {type(exc).__name__}: {exc}",
            ) from exc
        finally:
            tenant_db.close()
