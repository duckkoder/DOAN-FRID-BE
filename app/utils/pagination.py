"""Pagination utilities."""
from typing import List, TypeVar, Generic
from pydantic import BaseModel


T = TypeVar('T')


class PaginationParams(BaseModel):
    """Pagination parameters."""
    
    skip: int = 0
    limit: int = 100
    
    @property
    def offset(self) -> int:
        """Get offset for database query."""
        return self.skip
    
    @property
    def page(self) -> int:
        """Get current page number (1-indexed)."""
        return (self.skip // self.limit) + 1 if self.limit > 0 else 1


class PaginatedResponse(BaseModel, Generic[T]):
    """Paginated response wrapper."""
    
    total: int
    page: int
    page_size: int
    total_pages: int
    data: List[T]
    
    model_config = {"from_attributes": True}
    
    @classmethod
    def create(cls, data: List[T], total: int, pagination: PaginationParams):
        """
        Create paginated response.
        
        Args:
            data: List of items
            total: Total number of items
            pagination: Pagination parameters
            
        Returns:
            PaginatedResponse instance
        """
        total_pages = (total + pagination.limit - 1) // pagination.limit if pagination.limit > 0 else 1
        
        return cls(
            total=total,
            page=pagination.page,
            page_size=pagination.limit,
            total_pages=total_pages,
            data=data
        )
