"""Department model - Quản lý các khoa/phòng ban."""
from sqlalchemy import Column, String
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class Department(BaseModel):
    """Department model - 1 Department có nhiều Specializations."""
    
    __tablename__ = "departments"
    
    name = Column(String(100), unique=True, nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    
    # Relationships
    specializations = relationship(
        "Specialization", 
        back_populates="department", 
        cascade="all, delete-orphan"
    )
    teachers = relationship("Teacher", back_populates="department")
    
    def __repr__(self):
        return f"<Department(id={self.id}, name={self.name}, code={self.code})>"
