"""Base schemas and common Pydantic models."""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    
    model_config = ConfigDict(from_attributes=True)


class TimestampSchema(BaseSchema):
    """Schema with timestamp fields."""
    
    created_at: datetime
    updated_at: datetime


class ResponseBase(BaseSchema):
    """Base response schema."""
    
    id: int
    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Pagination parameters."""
    
    skip: int = 0
    limit: int = 100


class PaginatedResponse(BaseSchema):
    """Paginated response wrapper."""
    
    total: int
    skip: int
    limit: int
    data: list
