"""Platform-managed environment configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import dotenv_values, set_key
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
    target_file: str = "backend"


class PlatformEnvConfigService:
    """Read and update a small whitelist of safe .env keys."""

    AI_MODEL_SPECS: tuple[EnvConfigSpec, ...] = (
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

    SECURITY_SPECS: tuple[EnvConfigSpec, ...] = (
        EnvConfigSpec("ACCESS_TOKEN_EXPIRE_MINUTES", "Access token lifetime", "Dang nhap", "int", "Minutes before tenant/platform access tokens expire. 120 minutes is about 2 hours."),
        EnvConfigSpec("REFRESH_TOKEN_EXPIRE_DAYS", "Refresh token lifetime", "Dang nhap", "int", "Days a refresh token remains valid if it is not revoked by logout or admin action."),
        EnvConfigSpec("AI_WEBSOCKET_TOKEN_EXPIRE_MINUTES", "AI attendance session token", "Diem danh realtime", "int", "Minutes before the WebSocket token used by realtime attendance expires. Use about 120 minutes for long classes."),
    )

    @classmethod
    def list_items(cls, specs: tuple[EnvConfigSpec, ...] | None = None) -> dict[str, list[dict[str, Any]]]:
        selected_specs = specs or cls.AI_MODEL_SPECS
        return {"items": [cls._serialize_spec(spec) for spec in selected_specs]}

    @classmethod
    def update_items(
        cls,
        values: dict[str, Any],
        actor: PlatformUser,
        specs: tuple[EnvConfigSpec, ...] | None = None,
    ) -> dict[str, list[dict[str, Any]]]:
        selected_specs = specs or cls.AI_MODEL_SPECS
        specs_by_key = {spec.key: spec for spec in selected_specs}
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
            target_env_path = cls._target_env_path(spec)
            set_key(target_env_path, key, normalized_value)
            os.environ[key] = normalized_value
            if spec.target_file == "backend":
                cls._update_runtime_setting(spec, normalized_value)

        return cls.list_items(selected_specs)

    @classmethod
    def list_security_items(cls) -> dict[str, list[dict[str, Any]]]:
        return cls.list_items(cls.SECURITY_SPECS)

    @classmethod
    def update_security_items(cls, values: dict[str, Any], actor: PlatformUser) -> dict[str, list[dict[str, Any]]]:
        return cls.update_items(values, actor, cls.SECURITY_SPECS)

    @classmethod
    def _serialize_spec(cls, spec: EnvConfigSpec) -> dict[str, Any]:
        raw_value = cls._coerce_display_value(spec, cls._read_value(spec))
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
    def _candidate_env_paths(target_file: str) -> list[str]:
        filename = ".env.ai" if target_file == "ai" else ".env.backend"
        env_var = "AI_ENV_FILE" if target_file == "ai" else "BACKEND_ENV_FILE"
        infra_path = os.path.abspath(os.path.join(project_root, "..", "infra", filename))
        return [
            os.environ.get(env_var, ""),
            os.path.join(project_root, filename),
            os.path.join("/app", filename),
            os.path.join("/home/ubuntu/frid", filename),
            infra_path,
            env_path,
        ]

    @classmethod
    def _target_env_path(cls, spec: EnvConfigSpec) -> str:
        for path in cls._candidate_env_paths(spec.target_file):
            if path and os.path.exists(path):
                return path

        fallback = cls._candidate_env_paths(spec.target_file)[0]
        if fallback:
            return fallback
        return env_path

    @classmethod
    def _read_value(cls, spec: EnvConfigSpec) -> Any:
        target_path = cls._target_env_path(spec)
        file_values = dotenv_values(target_path) if os.path.exists(target_path) else {}
        if spec.key in file_values:
            return file_values[spec.key]
        if spec.target_file == "backend":
            return getattr(settings, spec.key, None)
        return os.environ.get(spec.key)

    @staticmethod
    def _coerce_display_value(spec: EnvConfigSpec, value: Any) -> Any:
        if value is None or value == "":
            return value
        if spec.value_type == "bool":
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"true", "1", "yes", "on"}
        if spec.value_type == "int":
            return int(value)
        if spec.value_type == "float":
            return float(value)
        return value

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
