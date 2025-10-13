"""Authentication service for user registration, login, and token management."""
from datetime import datetime, timedelta
from typing import Optional, TYPE_CHECKING
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.schemas.auth import RegisterRequest, LoginRequest
from app.core.security import (
    get_password_hash,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)

from app.models.user import User
from app.models.teacher import Teacher
from app.models.student import Student
from app.models.refresh_token import RefreshToken


class AuthService:
    """Service class for authentication operations."""

    @staticmethod
    async def register(db: Session, request: RegisterRequest) -> dict:
        """Register a new user (teacher or student)."""
        
        existing_user = db.query(User).filter(User.email == request.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        if request.role == "teacher" and request.teacher_code:
            existing_teacher = db.query(Teacher).filter(
                Teacher.teacher_code == request.teacher_code
            ).first()
            if existing_teacher:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Teacher code already exists"
                )
        
        if request.role == "student" and request.student_code:
            existing_student = db.query(Student).filter(
                Student.student_code == request.student_code
            ).first()
            if existing_student:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Student code already exists"
                )
        
        hashed_password = get_password_hash(request.password)
        new_user = User(
            full_name=request.full_name,
            email=request.email,
            password_hash=hashed_password,
            role=request.role,
            phone=request.phone,
            is_active=True,
            is_verified=False,
        )
        db.add(new_user)
        db.flush()
        
        if request.role == "teacher":
            teacher = Teacher(
                user_id=new_user.id,
                teacher_code=request.teacher_code,
                department=request.department,
            )
            db.add(teacher)
        elif request.role == "student":
            student = Student(
                user_id=new_user.id,
                student_code=request.student_code,
                major=request.major,
                academic_year=request.academic_year,
            )
            db.add(student)
        
        access_token, refresh_token_str = AuthService._generate_tokens(db, new_user)
        
        db.commit()
        db.refresh(new_user)
        
        user_data = AuthService._build_user_response(db, new_user)
        
        return {
            "user": user_data,
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer"
        }

    @staticmethod
    async def login(db: Session, request: LoginRequest) -> dict:
        """Authenticate user and return tokens."""
        
        user = db.query(User).filter(User.email == request.email).first()
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not verify_password(request.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        if not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is deactivated. Please contact administrator."
            )
        
        access_token, refresh_token_str = AuthService._generate_tokens(db, user)
        db.commit()
        
        user_data = AuthService._build_user_response(db, user)
        
        return {
            "user": user_data,
            "access_token": access_token,
            "refresh_token": refresh_token_str,
            "token_type": "bearer"
        }

    @staticmethod
    async def refresh_token(db: Session, refresh_token_str: str) -> dict:
        """Generate new access token using refresh token."""
        
        payload = decode_token(refresh_token_str)
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )
        
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token_str
        ).first()
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found"
            )
        
        if token_record.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked"
            )
        
        if token_record.expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )
        
        user = db.query(User).filter(User.id == token_record.user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User not found or deactivated"
            )
        
        token_record.revoked_at = datetime.utcnow()
        
        new_access_token, new_refresh_token_str = AuthService._generate_tokens(db, user)
        db.commit()
        
        return {
            "access_token": new_access_token,
            "refresh_token": new_refresh_token_str,
            "token_type": "bearer"
        }

    @staticmethod
    async def logout(db: Session, refresh_token_str: str) -> dict:
        """Revoke refresh token (logout)."""
        
        token_record = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token_str
        ).first()
        
        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Refresh token not found"
            )
        
        if token_record.revoked_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token already revoked"
            )
        
        token_record.revoked_at = datetime.utcnow()
        db.commit()
        
        return {"message": "Logged out successfully"}

    @staticmethod
    def _generate_tokens(db: Session, user) -> tuple[str, str]:
        """Generate access and refresh tokens."""
        
        token_data = {"sub": user.email, "user_id": user.id, "role": user.role}
        
        access_token = create_access_token(token_data)
        refresh_token_str = create_refresh_token(token_data)
        
        refresh_token = RefreshToken(
            user_id=user.id,
            token=refresh_token_str,
            expires_at=datetime.utcnow() + timedelta(days=7),
            revoked_at=None,
        )
        db.add(refresh_token)
        
        return access_token, refresh_token_str
    
    @staticmethod
    def _build_user_response(db: Session, user) -> dict:
        """Build user response with role-specific data."""
        
        user_data = {
            "id": user.id,
            "full_name": user.full_name,
            "email": user.email,
            "role": user.role,
            "is_active": user.is_active,
            "avatar_url": user.avatar_url,
            "phone": user.phone,
            "is_verified": user.is_verified,
            "created_at": user.created_at,
        }
        
        if user.role == "teacher":
            teacher = db.query(Teacher).filter(Teacher.user_id == user.id).first()
            if teacher:
                user_data["teacher_code"] = teacher.teacher_code
                user_data["department"] = teacher.department
        elif user.role == "student":
            student = db.query(Student).filter(Student.user_id == user.id).first()
            if student:
                user_data["student_code"] = student.student_code
                user_data["major"] = student.major
                user_data["academic_year"] = student.academic_year
        
        return user_data
