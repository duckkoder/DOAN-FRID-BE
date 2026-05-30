"""Platform SQLAlchemy models."""
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import declarative_base


PlatformBase = declarative_base()
VIETNAM_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def get_vietnam_time():
    return datetime.now(VIETNAM_TZ)


class PlatformBaseModel(PlatformBase):
    """Base class for platform tables."""

    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=get_vietnam_time,
        onupdate=get_vietnam_time,
        nullable=False,
    )


from app.platform.models.platform_user import PlatformUser  # noqa: E402,F401
from app.platform.models.tenant import Tenant  # noqa: E402,F401

