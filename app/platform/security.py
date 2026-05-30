"""Authentication dependencies for platform APIs."""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.platform.database import get_platform_db
from app.platform.models.platform_user import PlatformUser


platform_security = HTTPBearer()


async def get_current_platform_user(
    credentials: HTTPAuthorizationCredentials = Depends(platform_security),
    db: Session = Depends(get_platform_db),
) -> PlatformUser:
    """Resolve the current platform user from a platform-scoped JWT."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("scope") != "platform":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired platform token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    role = payload.get("role")
    if not user_id or role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin role required",
        )

    user = db.query(PlatformUser).filter(PlatformUser.id == user_id).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform user is inactive or missing",
        )
    return user

