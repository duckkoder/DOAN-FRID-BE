"""Tenant registry model."""
from sqlalchemy import Column, Integer, String, UniqueConstraint

from app.platform.models import PlatformBaseModel


class Tenant(PlatformBaseModel):
    """Tenant metadata stored in the platform database."""

    __tablename__ = "tenants"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_tenants_slug"),
        UniqueConstraint("school_code", name="uq_tenants_school_code"),
    )

    name = Column(String(255), nullable=False)
    school_code = Column(String(100), nullable=False, index=True)
    slug = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="active")

    db_name = Column(String(255), nullable=False)
    db_host = Column(String(255), nullable=False)
    db_port = Column(Integer, nullable=False, default=5432)
    db_user = Column(String(255), nullable=False)
    db_password_encrypted = Column(String(1024), nullable=False)

    storage_provider = Column(String(50), nullable=False, default="s3")
    storage_bucket = Column(String(255), nullable=True)
    storage_region = Column(String(100), nullable=True)
    storage_prefix = Column(String(255), nullable=False)
    logo_key = Column(String(500), nullable=True)
    logo_url = Column(String(500), nullable=True)
