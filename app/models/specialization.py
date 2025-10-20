"""Specialization model - Quản lý các chuyên ngành."""
from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Specialization(BaseModel):
    """Specialization model - thuộc về 1 Department."""
    
    __tablename__ = "specializations"
    
    name = Column(String(100), nullable=False)
    code = Column(String(20), nullable=False, index=True)
    description = Column(String(500), nullable=True)
    
    # Foreign Keys
    department_id = Column(
        Integer, 
        ForeignKey("departments.id", ondelete="CASCADE"), 
        nullable=False
    )
    
    # Relationships
    department = relationship("Department", back_populates="specializations")
    teachers = relationship("Teacher", back_populates="specialization")
    
    def __repr__(self):
        return f"<Specialization(id={self.id}, name={self.name}, code={self.code})>"
