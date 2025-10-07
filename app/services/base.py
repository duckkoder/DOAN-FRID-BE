"""Base service class for business logic."""
from typing import Generic, TypeVar, Type
from sqlalchemy.orm import Session
from app.repositories.base import BaseRepository


RepositoryType = TypeVar("RepositoryType", bound=BaseRepository)


class BaseService(Generic[RepositoryType]):
    """Base service class with common business logic patterns."""
    
    def __init__(self, repository_class: Type[RepositoryType], db: Session):
        """
        Initialize service.
        
        Args:
            repository_class: Repository class to use
            db: Database session
        """
        self.repository = repository_class(db)
        self.db = db
    
    def get_by_id(self, id: int):
        """
        Get entity by ID.
        
        Args:
            id: Entity ID
            
        Returns:
            Entity or None
        """
        return self.repository.get(id)
    
    def get_all(self, skip: int = 0, limit: int = 100):
        """
        Get all entities with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of entities
        """
        return self.repository.get_all(skip=skip, limit=limit)
    
    def create(self, data: dict):
        """
        Create a new entity.
        
        Args:
            data: Entity data
            
        Returns:
            Created entity
        """
        return self.repository.create(data)
    
    def update(self, id: int, data: dict):
        """
        Update an entity.
        
        Args:
            id: Entity ID
            data: Update data
            
        Returns:
            Updated entity or None
        """
        return self.repository.update(id, data)
    
    def delete(self, id: int) -> bool:
        """
        Delete an entity.
        
        Args:
            id: Entity ID
            
        Returns:
            True if deleted, False otherwise
        """
        return self.repository.delete(id)
