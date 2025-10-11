"""Models module for SQLAlchemy ORM entities."""
"""Models module for SQLAlchemy ORM entities."""
from app.models.base import Base, BaseModel
from app.models.test import Test  # ✅ Thêm dòng này

# Import tất cả models để Alembic detect được
__all__ = [
    "Base",
    "BaseModel",
    "Test",  # ✅ Thêm vào list
]