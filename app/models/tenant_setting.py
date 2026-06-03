"""Tenant-owned non-secret configuration values."""
from sqlalchemy import Column, ForeignKey, Integer, String, Text, UniqueConstraint

from app.models.base import BaseModel


class TenantSetting(BaseModel):
    """Config values that tenant admins can manage directly."""

    __tablename__ = "tenant_settings"
    __table_args__ = (UniqueConstraint("key_name", name="uq_tenant_settings_key_name"),)

    key_name = Column(String(100), nullable=False, index=True)
    value = Column(Text, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
