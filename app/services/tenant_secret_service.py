"""Service for encrypted tenant-owned API keys."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.crypto import decrypt_secret, encrypt_secret
from app.models.tenant_secret import TenantSecret
from app.models.user import User


class TenantSecretService:
    """Manage tenant secrets without returning plaintext values."""

    @staticmethod
    def _require_admin(current_user: User) -> None:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required",
            )

    @staticmethod
    def list_secrets(db: Session, current_user: User) -> dict:
        TenantSecretService._require_admin(current_user)
        secrets = db.query(TenantSecret).order_by(TenantSecret.key_name.asc()).all()
        return {
            "secrets": [
                {
                    "key_name": secret.key_name,
                    "configured": True,
                    "status": secret.status,
                    "updated_at": secret.updated_at,
                }
                for secret in secrets
            ]
        }

    @staticmethod
    def upsert_secret(db: Session, current_user: User, key_name: str, value: str) -> dict:
        TenantSecretService._require_admin(current_user)
        normalized_key = key_name.strip().lower()
        if not normalized_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key_name is required")

        secret = db.query(TenantSecret).filter(TenantSecret.key_name == normalized_key).first()
        encrypted_value = encrypt_secret(value)
        if secret:
            secret.encrypted_value = encrypted_value
            secret.status = "active"
            secret.updated_by = current_user.id
        else:
            secret = TenantSecret(
                key_name=normalized_key,
                encrypted_value=encrypted_value,
                status="active",
                created_by=current_user.id,
                updated_by=current_user.id,
            )
            db.add(secret)

        db.commit()
        db.refresh(secret)
        return {
            "key_name": secret.key_name,
            "configured": True,
            "status": secret.status,
            "updated_at": secret.updated_at,
        }

    @staticmethod
    def delete_secret(db: Session, current_user: User, key_name: str) -> dict:
        TenantSecretService._require_admin(current_user)
        normalized_key = key_name.strip().lower()
        secret = db.query(TenantSecret).filter(TenantSecret.key_name == normalized_key).first()
        if not secret:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Secret not found")
        db.delete(secret)
        db.commit()
        return {"message": "Secret deleted"}

    @staticmethod
    def get_plain_secret(db: Session, key_name: str) -> str | None:
        """Return decrypted active secret for internal backend use only."""
        normalized_key = key_name.strip().lower()
        secret = (
            db.query(TenantSecret)
            .filter(TenantSecret.key_name == normalized_key, TenantSecret.status == "active")
            .first()
        )
        if not secret:
            return None
        return decrypt_secret(secret.encrypted_value)
