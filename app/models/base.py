"""Base model with common fields for all database models."""
from datetime import datetime
from zoneinfo import ZoneInfo
from sqlalchemy import Column, Integer, DateTime
from sqlalchemy.ext.declarative import declarative_base


Base = declarative_base()

# ✅ Vietnam timezone for consistent datetime across the app
VIETNAM_TZ = ZoneInfo('Asia/Ho_Chi_Minh')


def get_vietnam_time():
    """Get current time in Vietnam timezone."""
    return datetime.now(VIETNAM_TZ)


class BaseModel(Base):
    """Base model class with common fields."""
    
    __abstract__ = True
    
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    created_at = Column(DateTime(timezone=True), default=get_vietnam_time, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=get_vietnam_time, onupdate=get_vietnam_time, nullable=False)
    
    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"
