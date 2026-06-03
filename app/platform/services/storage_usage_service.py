"""Storage usage inspection for platform tenants."""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.platform.models.tenant import Tenant
from app.platform.services.tenant_service import TenantService


class TenantStorageUsageService:
    """Read object metadata from S3 for tenant storage management."""

    CATEGORY_LABELS = {
        "face_registration": "Ảnh đăng ký khuôn mặt",
        "attendance_faces": "Ảnh điểm danh",
        "documents": "Tài liệu lớp học",
        "leave_evidence": "Minh chứng nghỉ phép",
        "avatars": "Ảnh đại diện",
        "avatar": "Ảnh đại diện",
        "temporary": "File tạm",
        "temp": "File tạm",
    }

    @classmethod
    def inspect_all(cls, db: Session) -> list[dict[str, Any]]:
        tenants = TenantService.list_tenants(db)
        try:
            cls.ensure_platform_folder()
        except (NoCredentialsError, BotoCoreError, ClientError):
            pass
        return [cls.inspect_tenant(tenant.id, db) for tenant in tenants]

    @classmethod
    def inspect_tenant(cls, tenant_id: int, db: Session) -> dict[str, Any]:
        tenant = TenantService.get_tenant(tenant_id, db)
        bucket = cls._effective_bucket(tenant)
        region = tenant.storage_region or settings.AWS_REGION
        prefixes = cls._tenant_prefixes(tenant)
        scanned_at = datetime.now(timezone.utc)

        try:
            client = cls._client(region)
            cls._ensure_folder_markers(client, bucket, tenant.school_code)
            usage = cls._scan_prefixes(client, bucket, prefixes)
            return {
                "tenant_id": tenant.id,
                "name": tenant.name,
                "school_code": tenant.school_code,
                "storage_provider": tenant.storage_provider,
                "bucket": bucket,
                "region": region,
                "prefixes": prefixes,
                "object_count": usage["object_count"],
                "total_bytes": usage["total_bytes"],
                "total_mb": round(usage["total_bytes"] / 1024 / 1024, 2),
                "categories": cls._category_rows(usage["categories"]),
                "last_modified": usage["last_modified"],
                "scanned_at": scanned_at,
                "status": "ok",
                "message": None,
            }
        except (NoCredentialsError, BotoCoreError, ClientError) as exc:
            return cls._error_response(tenant, bucket, region, prefixes, scanned_at, exc)

    @classmethod
    def _client(cls, region: str):
        return boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=region,
        )

    @classmethod
    def ensure_platform_folder(cls) -> None:
        region = settings.AWS_REGION
        bucket = settings.AWS_S3_BUCKET_NAME
        prefix = settings.PLATFORM_STORAGE_PREFIX.strip("/").rstrip("/")
        if not prefix:
            return
        client = cls._client(region)
        client.put_object(
            Bucket=bucket,
            Key=f"{prefix}/",
            Body=b"",
            ContentType="application/x-directory",
        )

    @classmethod
    def _effective_bucket(cls, tenant: Tenant) -> str:
        # Legacy tenants used generated names like bucket-s3-dut, but the app now
        # keeps one real S3 bucket and separates tenants by prefix.
        if tenant.storage_bucket and not tenant.storage_bucket.startswith("bucket-s3-"):
            return tenant.storage_bucket
        return settings.AWS_S3_BUCKET_NAME

    @classmethod
    def _tenant_prefixes(cls, tenant: Tenant) -> list[str]:
        canonical = f"{tenant.school_code}/"
        stored = tenant.storage_prefix or canonical
        if stored.strip("/").startswith(f"tenants/{tenant.school_code}"):
            stored = canonical
        candidates = [stored, canonical]

        prefixes: list[str] = []
        seen: set[str] = set()
        for raw in candidates:
            if not raw:
                continue
            prefix = raw.strip().lstrip("/")
            if prefix and not prefix.endswith("/"):
                prefix = f"{prefix}/"
            if prefix and prefix not in seen:
                prefixes.append(prefix)
                seen.add(prefix)
        return prefixes

    @classmethod
    def _scan_prefixes(cls, client, bucket: str, prefixes: list[str]) -> dict[str, Any]:
        seen_keys: set[str] = set()
        categories: dict[str, dict[str, int]] = defaultdict(lambda: {"object_count": 0, "total_bytes": 0})
        total_bytes = 0
        object_count = 0
        last_modified: datetime | None = None

        paginator = client.get_paginator("list_objects_v2")
        for prefix in prefixes:
            for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                for item in page.get("Contents", []):
                    key = item.get("Key")
                    if not key or key in seen_keys:
                        continue
                    if key.endswith("/") and int(item.get("Size") or 0) == 0:
                        continue
                    seen_keys.add(key)

                    size = int(item.get("Size") or 0)
                    modified = item.get("LastModified")
                    category = cls._classify_key(key)
                    if category == "other":
                        continue

                    object_count += 1
                    total_bytes += size
                    categories[category]["object_count"] += 1
                    categories[category]["total_bytes"] += size

                    if modified and (last_modified is None or modified > last_modified):
                        last_modified = modified

        return {
            "object_count": object_count,
            "total_bytes": total_bytes,
            "categories": categories,
            "last_modified": last_modified,
        }

    @classmethod
    def _ensure_folder_markers(cls, client, bucket: str, school_code: str) -> None:
        prefix = school_code.strip("/").rstrip("/")
        if not prefix:
            return

        for folder in settings.TENANT_STORAGE_FOLDERS_LIST:
            client.put_object(
                Bucket=bucket,
                Key=f"{prefix}/{folder}/",
                Body=b"",
                ContentType="application/x-directory",
            )

    @classmethod
    def _classify_key(cls, key: str) -> str:
        normalized = key.lower()
        if "/avatar/" in normalized or "avatar" in normalized:
            return "avatar"
        if "/face_registration/" in normalized or "face_registration" in normalized or "/face/" in normalized or "/faces/" in normalized:
            return "face_registration"
        if "/attendance_faces/" in normalized or "attendance" in normalized or "spoof" in normalized:
            return "attendance_faces"
        if "/documents/" in normalized or "document" in normalized or "/docs/" in normalized or "/materials/" in normalized:
            return "documents"
        if "/leave_evidence/" in normalized or "leave" in normalized or "evidence" in normalized or "proof" in normalized:
            return "leave_evidence"
        if "/temp/" in normalized or normalized.startswith("temp/"):
            return "temp"
        return "other"

    @classmethod
    def _category_rows(cls, categories: dict[str, dict[str, int]]) -> list[dict[str, Any]]:
        rows = []
        for category in settings.TENANT_STORAGE_FOLDERS_LIST:
            label = cls.CATEGORY_LABELS.get(category, category)
            data = categories.get(category, {"object_count": 0, "total_bytes": 0})
            rows.append(
                {
                    "category": category,
                    "label": label,
                    "object_count": data["object_count"],
                    "total_bytes": data["total_bytes"],
                }
            )
        return rows

    @classmethod
    def _error_response(
        cls,
        tenant: Tenant,
        bucket: str,
        region: str,
        prefixes: list[str],
        scanned_at: datetime,
        exc: Exception,
    ) -> dict[str, Any]:
        return {
            "tenant_id": tenant.id,
            "name": tenant.name,
            "school_code": tenant.school_code,
            "storage_provider": tenant.storage_provider,
            "bucket": bucket,
            "region": region,
            "prefixes": prefixes,
            "object_count": 0,
            "total_bytes": 0,
            "total_mb": 0,
            "categories": cls._category_rows({}),
            "last_modified": None,
            "scanned_at": scanned_at,
            "status": "error",
            "message": str(exc),
        }
