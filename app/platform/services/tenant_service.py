"""Tenant CRUD and lifecycle service."""
import secrets
import logging

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.crypto import encrypt_secret
from app.database.tenant_session import reset_tenant_sessionmaker
from app.platform.models.tenant import Tenant
from app.platform.schemas import TenantCreateRequest, TenantUpdateRequest
from app.platform.tenant_provisioning import (
    create_tenant_database,
    ensure_tenant_extensions,
    run_tenant_migrations,
)

logger = logging.getLogger(__name__)


def _db_safe_code(school_code: str) -> str:
    return school_code.replace("-", "_").replace("__", "_")


def get_tenant_or_404(db: Session, tenant_id: int) -> Tenant:
    """Lấy tenant theo ID hoặc raise 404."""
    tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Không tìm thấy tenant",
        )
    return tenant


def get_public_tenant_by_slug_or_404(db: Session, slug: str) -> Tenant:
    """Load active tenant public metadata by slug."""
    normalized_slug = slug.strip().lower()
    tenant = db.query(Tenant).filter(Tenant.slug == normalized_slug).first()
    if not tenant or tenant.status != "active":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


def get_effective_storage_bucket(tenant: Tenant) -> str:
    """Return the real S3 bucket. Legacy tenants may store generated bucket names."""
    if tenant.storage_bucket and not tenant.storage_bucket.startswith("bucket-s3-"):
        return tenant.storage_bucket
    return settings.AWS_S3_BUCKET_NAME


def ensure_tenant_storage_folders(tenant: Tenant) -> None:
    """Create tenant folder markers in the configured S3 bucket."""
    if tenant.storage_provider != "s3":
        return

    bucket = get_effective_storage_bucket(tenant)
    region = tenant.storage_region or settings.AWS_REGION
    prefix = tenant.storage_prefix.strip("/").rstrip("/")
    if not prefix:
        return

    client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=region,
    )

    for folder in settings.TENANT_STORAGE_FOLDERS_LIST:
        client.put_object(
            Bucket=bucket,
            Key=f"{prefix}/{folder}/",
            Body=b"",
            ContentType="application/x-directory",
        )


class TenantService:

    @staticmethod
    def list_tenants(db: Session) -> list[Tenant]:
        """Danh sách tất cả tenant, mới nhất trước."""
        return db.query(Tenant).order_by(Tenant.created_at.desc()).all()

    @staticmethod
    def list_public_tenants(db: Session) -> list[Tenant]:
        """Public active tenant list for the homepage partner selector."""
        return (
            db.query(Tenant)
            .filter(Tenant.status == "active")
            .order_by(Tenant.name.asc())
            .all()
        )

    @staticmethod
    def get_tenant(tenant_id: int, db: Session) -> Tenant:
        """Chi tiết một tenant."""
        return get_tenant_or_404(db, tenant_id)

    @staticmethod
    def get_public_tenant(slug: str, db: Session) -> Tenant:
        """Public tenant metadata for tenant login page."""
        return get_public_tenant_by_slug_or_404(db, slug)

    @staticmethod
    def update_tenant(tenant_id: int, request: TenantUpdateRequest, db: Session) -> Tenant:
        """Update tenant display metadata. School code/slug stays immutable."""
        tenant = get_tenant_or_404(db, tenant_id)
        tenant.name = request.name.strip()
        if request.logo_url is not None:
            tenant.logo_url = request.logo_url
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def create_tenant(request: TenantCreateRequest, db: Session) -> Tenant:
        """
        Tạo tenant mới:
        1. Validate slug không trùng
        2. Tạo PostgreSQL database + role
        3. Cài extension (pgvector…)
        4. Chạy Alembic migration
        5. Lưu vào platform DB
        """
        school_code = request.school_code
        existing = db.query(Tenant).filter(
            (Tenant.slug == school_code) | (Tenant.school_code == school_code)
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Mã trường '{school_code}' đã tồn tại",
            )

        db_code = _db_safe_code(school_code)
        tenant = Tenant(
            name=request.name,
            school_code=school_code,
            slug=school_code,
            status="active",
            db_name=f"frid_{db_code}_db",
            db_host=settings.TENANT_DB_HOST,
            db_port=settings.TENANT_DB_PORT,
            db_user=f"db_user_{db_code}",
            db_password_encrypted=encrypt_secret(secrets.token_urlsafe(24)),
            storage_provider=request.storage_provider,
            storage_bucket=settings.AWS_S3_BUCKET_NAME,
            storage_region=request.storage_region,
            storage_prefix=f"{school_code}/",
            logo_url=request.logo_url,
        )
        db.add(tenant)
        try:
            db.flush()
            create_tenant_database(tenant)
            ensure_tenant_extensions(tenant)
            run_tenant_migrations(tenant)
            ensure_tenant_storage_folders(tenant)
            db.commit()
            db.refresh(tenant)
            logger.info(
                "platform.tenant.created tenant_id=%s school_code=%s",
                tenant.id, tenant.school_code,
            )
            return tenant
        except HTTPException:
            db.rollback()
            raise
        except (BotoCoreError, ClientError) as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tạo folder S3 cho tenant thất bại: {exc}",
            ) from exc
        except Exception as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Tạo tenant thất bại: {type(exc).__name__}: {exc}",
            ) from exc

    @staticmethod
    def suspend_tenant(tenant_id: int, db: Session) -> Tenant:
        """Tạm khóa tenant."""
        tenant = get_tenant_or_404(db, tenant_id)
        if tenant.status == "suspended":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant đã bị tạm khóa rồi",
            )
        tenant.status = "suspended"
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def activate_tenant(tenant_id: int, db: Session) -> Tenant:
        """Kích hoạt lại tenant."""
        tenant = get_tenant_or_404(db, tenant_id)
        if tenant.status == "active":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tenant đang hoạt động rồi",
            )
        tenant.status = "active"
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def update_storage(tenant_id: int, fields: dict, db: Session) -> Tenant:
        """Cập nhật cấu hình storage (provider/bucket/region/prefix)."""
        tenant = get_tenant_or_404(db, tenant_id)
        for field, value in fields.items():
            setattr(tenant, field, value)
        db.commit()
        db.refresh(tenant)
        return tenant

    @staticmethod
    def update_db_connection(tenant_id: int, db_host: str, db_port: int, db: Session) -> Tenant:
        """
        Cập nhật db_host/db_port của tenant đã bị lưu sai.
        Cũng xóa cache engine cũ để lần sau connect lại từ đầu.
        """
        tenant = get_tenant_or_404(db, tenant_id)
        tenant.db_host = db_host
        tenant.db_port = db_port
        db.commit()
        db.refresh(tenant)
        # Xóa cached engine để buộc tạo lại với host mới
        reset_tenant_sessionmaker(tenant.id)
        return tenant
