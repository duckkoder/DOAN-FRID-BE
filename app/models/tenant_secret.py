"""Tenant-owned encrypted integration secrets."""
from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class TenantSecret(BaseModel):
    """Encrypted API keys/secrets configured by a tenant admin."""

    __tablename__ = "tenant_secrets"
    __table_args__ = (UniqueConstraint("key_name", name="uq_tenant_secrets_key_name"),)

    key_name = Column(String(100), nullable=False, index=True)
    encrypted_value = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="active")
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

