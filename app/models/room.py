from sqlalchemy import Column, Integer, String
from app.models.base import BaseModel

class Room(BaseModel):
    __tablename__ = "rooms"

    name = Column(String(50), nullable=False, unique=True, index=True)
    capacity = Column(Integer, nullable=False, default=50)
    description = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default="active")  # active, inactive
