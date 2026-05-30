"""Shared S3 client factory."""
import boto3

from app.core.config import settings


def create_s3_client():
    """Create a boto3 S3 client from application settings."""
    return boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION,
    )

