"""Platform-managed environment configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import set_key
from fastapi import HTTPException, status

from app.core.config import env_path, settings
from app.platform.models.platform_user import PlatformUser


@dataclass(frozen=True)
class EnvConfigSpec:
    key: str
    label: str
    group: str
    value_type: str
    description: str
    secret: bool = False
    restart_required: bool = False


class PlatformEnvConfigService:
    """Read and update a small whitelist of AI/model .env keys."""

    SPECS: tuple[EnvConfigSpec, ...] = (
        EnvConfigSpec("AI_CONFIDENCE_THRESHOLD", "AI confidence threshold", "Model", "float", "avg_confidence >= threshold means auto PRESENT; lower values go to pending teacher confirmation."),
        EnvConfigSpec("FACE_VERIFICATION_FPS", "Processing FPS", "Model", "int", "Number of frames per second used for face verification processing."),
        EnvConfigSpec("FACE_VERIFICATION_JPEG_QUALITY", "JPEG quality", "Model", "int", "JPEG compression quality. Suggested range: 70-90."),
        EnvConfigSpec("FACE_VERIFICATION_TIMEOUT", "Session timeout", "Model", "int", "Maximum face verification session duration in seconds."),
        EnvConfigSpec("FACE_VERIFICATION_MIN_FACE_WIDTH", "Minimum face width", "Model", "int", "Minimum detected face width in pixels before the frame is accepted."),
        EnvConfigSpec("FACE_VERIFICATION_FRAME_WIDTH", "Frame width", "Model", "int", "Frame width used for face verification processing."),
        EnvConfigSpec("FACE_VERIFICATION_FRAME_HEIGHT", "Frame height", "Model", "int", "Frame height used for face verification processing."),
        EnvConfigSpec("ATTENDANCE_ALLOW_CREATE_ANYTIME", "Allow create anytime", "Diem danh", "bool", "Allow teachers to create attendance sessions outside the class schedule window."),
        EnvConfigSpec("ATTENDANCE_CREATE_WINDOW_GRACE_MINUTES", "Schedule grace minutes", "Diem danh", "int", "Additional minutes allowed when checking the attendance creation schedule window."),
    )

    @classmethod
    def list_items(cls) -> dict[str, list[dict[str, Any]]]:
        return {"items": [cls._serialize_spec(spec) for spec in cls.SPECS]}

    @classmethod
    def update_items(cls, values: dict[str, Any], actor: PlatformUser) -> dict[str, list[dict[str, Any]]]:
        specs_by_key = {spec.key: spec for spec in cls.SPECS}
        unknown_keys = sorted(set(values) - set(specs_by_key))
        if unknown_keys:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported env keys: {', '.join(unknown_keys)}",
            )

        for key, raw_value in values.items():
            spec = specs_by_key[key]
            if spec.secret and (raw_value is None or str(raw_value).strip() == ""):
                continue

            normalized_value = cls._normalize_value(spec, raw_value)
            set_key(env_path, key, normalized_value)
            os.environ[key] = normalized_value
            cls._update_runtime_setting(spec, normalized_value)

        return cls.list_items()

    @classmethod
    def _serialize_spec(cls, spec: EnvConfigSpec) -> dict[str, Any]:
        raw_value = getattr(settings, spec.key, None)
        configured = raw_value is not None and str(raw_value) != ""
        return {
            "key": spec.key,
            "label": spec.label,
            "group": spec.group,
            "value": None if spec.secret else raw_value,
            "value_type": spec.value_type,
            "description": spec.description,
            "secret": spec.secret,
            "configured": configured,
            "restart_required": spec.restart_required,
        }

    @staticmethod
    def _normalize_value(spec: EnvConfigSpec, raw_value: Any) -> str:
        if raw_value is None:
            if spec.value_type == "string":
                return ""
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{spec.key} is required")

        if spec.value_type == "bool":
            if isinstance(raw_value, bool):
                return "true" if raw_value else "false"
            value = str(raw_value).strip().lower()
            if value in {"true", "1", "yes", "on"}:
                return "true"
            if value in {"false", "0", "no", "off"}:
                return "false"
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{spec.key} must be boolean")

        if spec.value_type == "int":
            try:
                value = int(raw_value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{spec.key} must be integer")
            if value < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{spec.key} must be >= 0")
            return str(value)

        if spec.value_type == "float":
            try:
                value = float(raw_value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{spec.key} must be number")
            if spec.key == "AI_CONFIDENCE_THRESHOLD" and not 0 <= value <= 1:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="AI_CONFIDENCE_THRESHOLD must be between 0 and 1")
            return str(value)

        return str(raw_value).strip()

    @staticmethod
    def _update_runtime_setting(spec: EnvConfigSpec, value: str) -> None:
        if spec.value_type == "bool":
            setattr(settings, spec.key, value.lower() == "true")
        elif spec.value_type == "int":
            setattr(settings, spec.key, int(value))
        elif spec.value_type == "float":
            setattr(settings, spec.key, float(value))
        else:
            setattr(settings, spec.key, value or None if spec.key.endswith("_PUBLIC_URL") else value)
