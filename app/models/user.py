"""User model - Base user entity for all roles."""
from sqlalchemy import Column, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from app.models.base import BaseModel


class User(BaseModel):
    """User model representing all system users (admin, teacher, student)."""
    
    __tablename__ = "users"
    
    full_name = Column(String(255), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)  # admin, teacher, student
    is_active = Column(Boolean, default=True)
    avatar_url = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    admin = relationship("Admin", back_populates="user", uselist=False, cascade="all, delete-orphan")
    teacher = relationship("Teacher", back_populates="user", uselist=False, cascade="all, delete-orphan")
    student = relationship("Student", back_populates="user", uselist=False, cascade="all, delete-orphan")
    files = relationship("File", back_populates="uploader", cascade="all, delete-orphan")
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")
    system_logs = relationship("SystemLog", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"
