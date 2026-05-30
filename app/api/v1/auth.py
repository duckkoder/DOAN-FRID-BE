"""Authentication endpoints."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.database.tenant_session import tenant_db_session_by_slug
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
    Student requires `student_code`.
    """
    from app.services.auth_service import AuthService
    
    result = await AuthService.register(db, request)
    return {
        "message": "User registered successfully",
        **result
    }


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Login with email and password."""
    from app.services.auth_service import AuthService

    if not request.tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="tenant_slug is required",
        )

    with tenant_db_session_by_slug(request.tenant_slug) as (tenant_db, tenant):
        result = await AuthService.login(tenant_db, request, tenant)
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
