"""Specialization service for business logic."""
from typing import List
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.specialization import Specialization
from app.models.department import Department
from app.repositories.base import BaseRepository
from app.schemas.specialization import SpecializationCreate, SpecializationUpdate


class SpecializationService:
    """Service for Specialization business logic."""
    
    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.repository = BaseRepository(Specialization, db)
    
    def get_all(self, skip: int = 0, limit: int = 100) -> List[Specialization]:
        """
        Get all specializations with pagination.
        
        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return
            
        Returns:
            List of specializations
        """
        return self.repository.get_all(skip=skip, limit=limit)
    
    def get_by_department(self, department_id: int) -> List[Specialization]:
        """
        Get all specializations for a specific department.
        
        Args:
            department_id: Department ID
            
        Returns:
            List of specializations
        """
        return self.db.query(Specialization).filter(
            Specialization.department_id == department_id
        ).all()
    
    def get_by_id(self, specialization_id: int) -> Specialization:
        """
        Get specialization by ID.
        
        Args:
            specialization_id: Specialization ID
            
        Returns:
            Specialization instance
            
        Raises:
            HTTPException: If specialization not found
        """
        specialization = self.repository.get(specialization_id)
        if not specialization:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Specialization with id {specialization_id} not found"
            )
        return specialization
    
    def create(self, specialization_data: SpecializationCreate) -> Specialization:
        """
        Create a new specialization.
        
        Args:
            specialization_data: Specialization creation data
            
        Returns:
            Created specialization
            
        Raises:
            HTTPException: If department not found or code conflict
        """
        # Validate department exists
        department = self.db.query(Department).filter(
            Department.id == specialization_data.department_id
        ).first()
        if not department:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Department with id {specialization_data.department_id} not found"
            )
        
        # Check if code exists in the same department
        existing = self.db.query(Specialization).filter(
            Specialization.code == specialization_data.code,
            Specialization.department_id == specialization_data.department_id
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Specialization with code '{specialization_data.code}' already exists in this department"
            )
        
        # Create specialization
        return self.repository.create(specialization_data.model_dump())
    
    def update(
        self, 
        specialization_id: int, 
        specialization_data: SpecializationUpdate
    ) -> Specialization:
        """
        Update a specialization.
        
        Args:
            specialization_id: Specialization ID
            specialization_data: Update data
            
        Returns:
            Updated specialization
            
        Raises:
            HTTPException: If specialization not found or validation fails
        """
        specialization = self.get_by_id(specialization_id)
        
        # Validate department if being changed
        if specialization_data.department_id:
            if specialization_data.department_id != specialization.department_id:
                department = self.db.query(Department).filter(
                    Department.id == specialization_data.department_id
                ).first()
                if not department:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Department with id {specialization_data.department_id} not found"
                    )
        
        # Check code uniqueness in department if code is being changed
        if specialization_data.code and specialization_data.code != specialization.code:
            target_dept_id = specialization_data.department_id or specialization.department_id
            existing = self.db.query(Specialization).filter(
                Specialization.code == specialization_data.code,
                Specialization.department_id == target_dept_id,
                Specialization.id != specialization_id
            ).first()
            
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Specialization with code '{specialization_data.code}' already exists in this department"
                )
        
        # Update only provided fields
        update_data = specialization_data.model_dump(exclude_unset=True)
        updated = self.repository.update(specialization_id, update_data)
        
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update specialization"
            )
        
        return updated
    
    def delete(self, specialization_id: int) -> bool:
        """
        Delete a specialization.
        
        Args:
            specialization_id: Specialization ID
            
        Returns:
            True if deleted
            
        Raises:
            HTTPException: If specialization not found or has dependencies
        """
        specialization = self.get_by_id(specialization_id)
        
        # Check if specialization is used by any teachers
        from app.models.teacher import Teacher
        teachers_count = self.db.query(Teacher).filter(
            Teacher.specialization_id == specialization_id
        ).count()
        
        if teachers_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot delete specialization. It is assigned to {teachers_count} teacher(s)."
            )
        
        success = self.repository.delete(specialization_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete specialization"
            )
        
        return True
    
    def get_with_department(self, specialization_id: int) -> Specialization:
        """
        Get specialization with its department loaded.
        
        Args:
            specialization_id: Specialization ID
            
        Returns:
            Specialization with department loaded
        """
        specialization = self.get_by_id(specialization_id)
        # Eager load department
        self.db.refresh(specialization, ["department"])
        return specialization
