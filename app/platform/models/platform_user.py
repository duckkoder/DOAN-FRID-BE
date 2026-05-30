"""Platform user model for super admin accounts."""
from sqlalchemy import Boolean, Column, DateTime, String

from app.platform.models import PlatformBaseModel


class PlatformUser(PlatformBaseModel):
    """User that belongs to the platform, not to a tenant."""

    __tablename__ = "platform_users"

    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="super_admin")
    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)

