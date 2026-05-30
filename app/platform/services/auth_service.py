"""Platform authentication service."""
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.platform.models.platform_user import PlatformUser


class PlatformAuthService:

    @staticmethod
    def login(email: str, password: str, db: Session) -> dict:
        """Xác thực super admin và trả về platform-scoped JWT."""
        user: PlatformUser | None = (
            db.query(PlatformUser).filter(PlatformUser.email == email).first()
        )

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email hoặc mật khẩu không đúng",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if user.role != "super_admin" or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tài khoản không có quyền đăng nhập platform",
            )

        user.last_login = datetime.utcnow()
        token = create_access_token(
            {
                "sub": user.email,
                "user_id": user.id,
                "role": user.role,
                "scope": "platform",
            }
        )
        db.commit()
        db.refresh(user)

        return {
            "message": "Đăng nhập thành công",
            "user": user,
            "access_token": token,
            "token_type": "bearer",
        }
