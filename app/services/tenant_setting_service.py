"""Service for tenant-owned non-secret settings."""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.tenant_setting import TenantSetting
from app.models.user import User


class TenantSettingService:
    """Manage tenant settings such as account email domains."""

    DEFAULTS = {
        "teacher_email_domain": "dut.udn.vn",
        "student_email_domain": "sv1.dut.udn.vn",
    }

    @staticmethod
    def _require_admin(current_user: User) -> None:
        if current_user.role != "admin":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required",
            )

    @staticmethod
    def _normalize_key(key_name: str) -> str:
        normalized_key = key_name.strip().lower()
        if not normalized_key:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="key_name is required")
        return normalized_key

    @staticmethod
    def _normalize_value(key_name: str, value: str) -> str:
        normalized = value.strip()
        if key_name.endswith("_email_domain"):
            normalized = normalized.removeprefix("@").lower()
            if "." not in normalized or " " in normalized:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Email domain is invalid",
                )
        if not normalized:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="value is required")
        return normalized

    @staticmethod
    def list_settings(db: Session, current_user: User) -> dict:
        TenantSettingService._require_admin(current_user)
        rows = db.query(TenantSetting).order_by(TenantSetting.key_name.asc()).all()
        values = {
            setting.key_name: {
                "key_name": setting.key_name,
                "value": setting.value,
                "updated_at": setting.updated_at,
            }
            for setting in rows
        }

        for key_name, value in TenantSettingService.DEFAULTS.items():
            values.setdefault(
                key_name,
                {
                    "key_name": key_name,
                    "value": value,
                    "updated_at": None,
                },
            )

        return {"settings": list(values.values())}

    @staticmethod
    def upsert_setting(db: Session, current_user: User, key_name: str, value: str) -> dict:
        TenantSettingService._require_admin(current_user)
        normalized_key = TenantSettingService._normalize_key(key_name)
        normalized_value = TenantSettingService._normalize_value(normalized_key, value)

        setting = db.query(TenantSetting).filter(TenantSetting.key_name == normalized_key).first()
        if setting:
            setting.value = normalized_value
            setting.updated_by = current_user.id
        else:
            setting = TenantSetting(
                key_name=normalized_key,
                value=normalized_value,
                created_by=current_user.id,
                updated_by=current_user.id,
            )
            db.add(setting)

        db.commit()
        db.refresh(setting)
        return {
            "key_name": setting.key_name,
            "value": setting.value,
            "updated_at": setting.updated_at,
        }

    @staticmethod
    def get_value(db: Session, key_name: str) -> str | None:
        normalized_key = TenantSettingService._normalize_key(key_name)
        setting = db.query(TenantSetting).filter(TenantSetting.key_name == normalized_key).first()
        if setting:
            return setting.value
        return TenantSettingService.DEFAULTS.get(normalized_key)
