"""Tenant-aware S3 storage service."""
from datetime import datetime
from uuid import uuid4

from botocore.exceptions import ClientError
from fastapi import HTTPException, status

from app.core.config import settings
from app.platform.models.tenant import Tenant
from app.storage.s3_client import create_s3_client


class TenantStorageService:
    """Generate tenant-scoped S3 object keys and presigned URLs."""

    def __init__(self):
        self.client = create_s3_client()

    def _bucket(self, tenant: Tenant) -> str:
        if tenant.storage_bucket and not tenant.storage_bucket.startswith("bucket-s3-"):
            return tenant.storage_bucket
        return settings.AWS_S3_BUCKET_NAME

    def _prefix(self, tenant: Tenant) -> str:
        prefix = tenant.storage_prefix or f"{tenant.slug}/"
        if prefix.strip("/").startswith(f"tenants/{tenant.slug}"):
            prefix = f"{tenant.slug}/"
        return prefix if prefix.endswith("/") else f"{prefix}/"

    def build_key(self, tenant: Tenant, folder: str, filename: str) -> str:
        safe_folder = folder.strip("/").replace("..", "")
        safe_name = filename.split("/")[-1].split("\\")[-1] or "file"
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        return f"{self._prefix(tenant)}{safe_folder}/{timestamp}_{uuid4().hex}_{safe_name}"

    def ensure_tenant_key(self, tenant: Tenant, key: str) -> None:
        if not key.startswith(self._prefix(tenant)):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Object key is outside tenant storage prefix",
            )

    def create_presigned_upload_url(
        self,
        tenant: Tenant,
        folder: str,
        filename: str,
        content_type: str,
        expires_in: int = 900,
    ) -> dict:
        key = self.build_key(tenant, folder, filename)
        bucket = self._bucket(tenant)
        try:
            url = self.client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": bucket,
                    "Key": key,
                    "ContentType": content_type or "application/octet-stream",
                },
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate upload URL: {exc}",
            ) from exc

        return {"upload_url": url, "bucket": bucket, "key": key, "expires_in": expires_in}

    def create_presigned_download_url(
        self,
        tenant: Tenant,
        key: str,
        expires_in: int = 900,
    ) -> dict:
        self.ensure_tenant_key(tenant, key)
        bucket = self._bucket(tenant)
        try:
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to generate download URL: {exc}",
            ) from exc

        return {"download_url": url, "bucket": bucket, "key": key, "expires_in": expires_in}


tenant_storage_service = TenantStorageService()
