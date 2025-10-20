"""Department service for business logic."""
from typing import Optional, List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.department import Department
from app.models.specialization import Specialization
from app.repositories.base import BaseRepository
from app.schemas.department import DepartmentCreate, DepartmentUpdate


class DepartmentService:
    """Service for Department business logic."""
    
    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repository = BaseRepository(Department, db)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Department]:
        """
        Get all departments with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of departments
        """
        return self.repository.get_all(skip=skip, limit=limit)
    
    def get_by_id(self, department_id: int) -> Department:
        """
        Get department by ID.
        
        Args:
            department_id: Department ID
            
        Returns:
            Department instance
            
        Raises:
            HTTPException: If department not found
        """
        department = self.repository.get(department_id)
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {department_id} not found"
            )
        return department
    
    def get_by_code(self, code: str) -> Optional[Department]:
        """
        Get department by code.
        
        Args:
            code: Department code
            
        Returns:
            Department instance or None
        """
        return self.db.query(Department).filter(Department.code == code).first()
    
    def create(self, department_data: DepartmentCreate) -> Department:
        """
        Create a new department.
        
        Args:
            department_data: Department creation data
            
        Returns:
            Created department
            
        Raises:
            HTTPException: If code or name already exists
        """
        # Check if code exists
        existing_code = self.get_by_code(department_data.code)
        if existing_code:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with code '{department_data.code}' already exists"
            )
        
        # Check if name exists
        existing_name = self.db.query(Department).filter(
            Department.name == department_data.name
        ).first()
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Department with name '{department_data.name}' already exists"
            )
        
        # Create department
        return self.repository.create(department_data.model_dump())
    
    def update(self, department_id: int, department_data: DepartmentUpdate) -> Department:
        """
        Update a department.
        
        Args:
            department_id: Department ID
            department_data: Update data
            
        Returns:
            Updated department
            
        Raises:
            HTTPException: If department not found or code/name conflict
        """
        department = self.get_by_id(department_id)
        
        # Check code uniqueness if being updated
        if department_data.code and department_data.code != department.code:
            existing_code = self.get_by_code(department_data.code)
            if existing_code:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department with code '{department_data.code}' already exists"
                )
        
        # Check name uniqueness if being updated
        if department_data.name and department_data.name != department.name:
            existing_name = self.db.query(Department).filter(
                Department.name == department_data.name,
                Department.id != department_id
            ).first()
            if existing_name:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Department with name '{department_data.name}' already exists"
                )
        
        # Update only provided fields
        update_data = department_data.model_dump(exclude_unset=True)
        updated = self.repository.update(department_id, update_data)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update department"
            )
        
        return updated
    
    def delete(self, department_id: int) -> bool:
        """
        Delete a department.
        
        Args:
            department_id: Department ID
            
        Returns:
            True if deleted
            
        Raises:
            HTTPException: If department not found or has dependencies
        """
        department = self.get_by_id(department_id)
        
        # Check if department has specializations
        specializations_count = self.db.query(Specialization).filter(
            Specialization.department_id == department_id
        ).count()
        
        if specializations_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete department. It has {specializations_count} specialization(s). Delete them first."
            )
        
        success = self.repository.delete(department_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete department"
            )
        
        return True
    
    def get_with_specializations(self, department_id: int) -> Department:
        """
        Get department with its specializations.
        
        Args:
            department_id: Department ID
            
        Returns:
            Department with specializations loaded
        """
        department = self.get_by_id(department_id)
        # Eager load specializations
        self.db.refresh(department, ["specializations"])
        return department
