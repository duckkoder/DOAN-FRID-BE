"""Test model for migration demonstration."""
from sqlalchemy import Column, String, Integer, Boolean, Text
from app.models.base import BaseModel


class Test(BaseModel):
    """Test table model."""

    __tablename__ = "test"

    # Các trường dữ liệu
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    score = Column(Integer, default=0)

    def __repr__(self):
        return f"<Test(id={self.id}, name='{self.name}')>"