"""Platform audit log model."""
from sqlalchemy import JSON, Column, ForeignKey, Integer, String, Text

from app.platform.models import PlatformBaseModel


class PlatformAuditLog(PlatformBaseModel):
    """Operational audit log stored in the platform database."""

    __tablename__ = "platform_audit_logs"

    actor_id = Column(Integer, ForeignKey("platform_users.id"), nullable=True, index=True)
    actor_email = Column(String(255), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)
    status = Column(String(50), nullable=False, default="success", index=True)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    tenant_school_code = Column(String(100), nullable=True, index=True)
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
