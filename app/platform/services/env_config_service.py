"""Platform-managed environment configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from dotenv import dotenv_values, set_key
from fastapi import HTTPException, status

from app.core.config import env_path, project_root, settings
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
        EnvConfigSpec("DETECTOR_CONF_THRESHOLD", "Detector confidence", "AI detection", "float", "Minimum confidence for face detector boxes.", target_file="ai"),
        EnvConfigSpec("DETECTOR_NMS_THRESHOLD", "Detector NMS", "AI detection", "float", "Non-maximum suppression threshold for face detection.", target_file="ai"),
        EnvConfigSpec("DETECTOR_PAD", "Detector padding", "AI detection", "int", "Padding pixels added around detected faces before recognition.", target_file="ai"),
        EnvConfigSpec("RECOGNIZER_THRESHOLD", "Recognition threshold", "AI recognition", "float", "Distance threshold used by the face recognizer.", target_file="ai"),
        EnvConfigSpec("RECOGNIZER_KNN_K", "KNN neighbors", "AI recognition", "int", "Number of nearest embeddings used for KNN voting.", target_file="ai"),
        EnvConfigSpec("RECOGNIZER_KNN_VOTING_THRESHOLD", "KNN vote threshold", "AI recognition", "float", "Minimum KNN voting score required for recognition.", target_file="ai"),
        EnvConfigSpec("ANTISPOOFING_THRESHOLD", "Anti-spoof threshold", "AI anti-spoofing", "float", "Minimum spoofing confidence threshold for anti-spoofing.", target_file="ai"),
        EnvConfigSpec("ANTISPOOFING_BLOCK_RECOGNITION", "Block spoof recognition", "AI anti-spoofing", "bool", "Block recognition results when anti-spoofing marks a face as fake.", target_file="ai"),
        EnvConfigSpec("REC_ENABLE_DYNAMIC_THRESHOLD", "Dynamic threshold", "AI recognition", "bool", "Enable identity-aware dynamic recognition threshold.", target_file="ai"),
        EnvConfigSpec("REC_IDENTITY_QUANTILE", "Identity quantile", "AI recognition", "float", "Quantile used to calculate identity-specific threshold.", target_file="ai"),
        EnvConfigSpec("REC_IDENTITY_MARGIN", "Identity margin", "AI recognition", "float", "Extra margin added to identity-specific threshold.", target_file="ai"),
        EnvConfigSpec("REC_IDENTITY_MIN_SCALE", "Identity min scale", "AI recognition", "float", "Minimum scale applied by dynamic threshold.", target_file="ai"),
        EnvConfigSpec("REC_MIN_CONFIDENCE", "Minimum confidence", "AI filtering", "float", "Minimum calibrated confidence required for a recognition result.", target_file="ai"),
        EnvConfigSpec("REC_MIN_VOTE_RATIO", "Minimum vote ratio", "AI filtering", "float", "Minimum vote ratio required across nearest neighbors.", target_file="ai"),
        EnvConfigSpec("REC_MIN_VALID_NEIGHBORS_RATIO", "Valid neighbors ratio", "AI filtering", "float", "Minimum ratio of valid neighbors required for recognition.", target_file="ai"),
        EnvConfigSpec("REC_REQUIRE_STABLE", "Require stable result", "AI filtering", "bool", "Require stable recognition across the validation window.", target_file="ai"),
        EnvConfigSpec("REC_MAX_DISTANCE_RATIO", "Max distance ratio", "AI filtering", "float", "Maximum distance ratio allowed for recognition.", target_file="ai"),
        EnvConfigSpec("RECOGNITION_CONFIRMATION_THRESHOLD", "Confirmation threshold", "AI validation", "int", "Number of successful recognitions required before confirming identity.", target_file="ai"),
        EnvConfigSpec("RECOGNITION_WINDOW_SIZE", "Recognition window", "AI validation", "int", "Number of frames used by recognition validation.", target_file="ai"),
        EnvConfigSpec("RECOGNITION_MIN_FRAME_SUCCESS_RATE", "Min frame success rate", "AI validation", "float", "Minimum successful-frame ratio required in the validation window.", target_file="ai"),
        EnvConfigSpec("RECOGNITION_DEBOUNCE_SECONDS", "Recognition debounce", "AI validation", "int", "Seconds to wait before confirming the same identity again.", target_file="ai"),
        EnvConfigSpec("ATTENDANCE_HEAVY_PROCESS_FACE_THRESHOLD", "Heavy process face threshold", "AI performance", "int", "Number of faces that switches AI service into heavier processing mode.", target_file="ai"),
        EnvConfigSpec("ATTENDANCE_HEAVY_PROCESS_INTERVAL", "Heavy process interval", "AI performance", "int", "Frame interval for heavy processing mode.", target_file="ai"),
        EnvConfigSpec("ATTENDANCE_RECOGNITION_CACHE_TTL_FRAMES", "Recognition cache TTL", "AI performance", "int", "Number of frames to keep recognition cache entries.", target_file="ai"),
    )

    SECURITY_SPECS: tuple[EnvConfigSpec, ...] = (
        EnvConfigSpec("ACCESS_TOKEN_EXPIRE_MINUTES", "Access token lifetime", "Dang nhap", "int", "Minutes before tenant/platform access tokens expire. 120 minutes is about 2 hours."),
        EnvConfigSpec("REFRESH_TOKEN_EXPIRE_DAYS", "Refresh token lifetime", "Dang nhap", "int", "Days a refresh token remains valid if it is not revoked by logout or admin action."),
        EnvConfigSpec("ATTENDANCE_ALLOW_CREATE_ANYTIME", "Allow create attendance anytime", "Van hanh", "bool", "Allow teachers to create attendance sessions outside the class schedule window."),
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
            set_key(target_env_path, key, normalized_value, quote_mode="never")
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

    @classmethod
    def _target_env_path(cls, spec: EnvConfigSpec) -> str:
        """Resolve the writable .env file path. Raises 500 if not found in production (write path)."""
        if cls._is_production():
            env_var = "AI_ENV_FILE" if spec.target_file == "ai" else "BACKEND_ENV_FILE"
            filename = ".env.ai" if spec.target_file == "ai" else ".env.backend"
            candidates = [
                os.environ.get(env_var, ""),
                os.path.join("/app", filename),
                os.path.join("/home/ubuntu/frid", filename),
            ]
            for target_path in candidates:
                if target_path and os.path.exists(target_path):
                    return target_path
            expected = " or ".join(path for path in candidates if path)
            if expected:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Production env file is not mounted: {expected}",
                )

        if spec.target_file == "ai":
            return os.path.abspath(os.path.join(project_root, "..", "ai-service", ".env"))
        return env_path

    @classmethod
    def _read_env_file_path(cls, spec: EnvConfigSpec) -> str | None:
        """Resolve the readable .env file path. Returns None if file not found (read path, never raises)."""
        if cls._is_production():
            env_var = "AI_ENV_FILE" if spec.target_file == "ai" else "BACKEND_ENV_FILE"
            filename = ".env.ai" if spec.target_file == "ai" else ".env.backend"
            candidates = [
                os.environ.get(env_var, ""),
                os.path.join("/app", filename),
                os.path.join("/home/ubuntu/frid", filename),
            ]
            for target_path in candidates:
                if target_path and os.path.exists(target_path):
                    return target_path
            return None  # File not accessible in container — use env vars instead

        if spec.target_file == "ai":
            return os.path.abspath(os.path.join(project_root, "..", "ai-service", ".env"))
        return env_path

    @staticmethod
    def _is_production() -> bool:
        environment = str(getattr(settings, "ENVIRONMENT", "") or os.environ.get("ENVIRONMENT", "")).strip().lower()
        if environment in {"production", "prod", "release"}:
            return True
        if os.path.exists("/app/.env.backend") or os.path.exists("/app/.env.ai"):
            return True
        return str(getattr(settings, "TENANT_DB_HOST", "")).strip().lower() == "db"

    @classmethod
    def _read_value(cls, spec: EnvConfigSpec) -> Any:
        """Read a config value: prefer .env file if accessible, else fall back to os.environ / settings."""
        target_path = cls._read_env_file_path(spec)
        if target_path and os.path.exists(target_path):
            file_values = dotenv_values(target_path)
            if spec.key in file_values:
                return file_values[spec.key]
        # Fallback: read from live environment (injected by docker-compose env_file)
        if spec.target_file == "backend":
            return getattr(settings, spec.key, None) or os.environ.get(spec.key)
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
