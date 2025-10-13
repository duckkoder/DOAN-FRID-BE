"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    LogoutResponse,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=RegisterResponse, status_code=status.HTTP_201_CREATED)
async def register(
    request: RegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user (teacher or student).
    Teacher requires `teacher_code`
    , Student requires `student_code`.
    """
    from app.services.auth_service import AuthService
    
    result = await AuthService.register(db, request)
    return {
        "message": "User registered successfully",
        **result
    }


@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: Session = Depends(get_db)
):
    """Login with email and password."""
    from app.services.auth_service import AuthService
    
    result = await AuthService.login(db, request)
    return {
        "message": "Login successful",
        **result
    }


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Require authentication
):
    """
    Refresh access token using refresh token.
    
    Requires: Valid JWT access token in Authorization header
    """
    from app.services.auth_service import AuthService
    
    result = await AuthService.refresh_token(db, request.refresh_token)
    return result


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    request: LogoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)  # ✅ Require authentication
):
    """
    Logout and revoke refresh token.
    
    Requires: Valid JWT access token in Authorization header
    """
    from app.services.auth_service import AuthService
    
    result = await AuthService.logout(db, request.refresh_token)
    return result