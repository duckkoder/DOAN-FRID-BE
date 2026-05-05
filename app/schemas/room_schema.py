from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class RoomBase(BaseModel):
    name: str = Field(..., max_length=50, description="Room name (e.g., A101)")
    capacity: int = Field(default=50, ge=1, description="Seating capacity")
    description: Optional[str] = Field(None, max_length=255)
    status: str = Field(default="active", description="active or inactive")

class RoomCreate(RoomBase):
    pass

class RoomUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=50)
    capacity: Optional[int] = Field(None, ge=1)
    description: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = None

class RoomResponse(RoomBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
