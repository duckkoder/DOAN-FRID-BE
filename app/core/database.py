"""Tenant-aware database dependency."""
from typing import Generator

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.database.tenant_session import tenant_db_session_by_slug


tenant_security = HTTPBearer()


def get_db(
    credentials: HTTPAuthorizationCredentials = Depends(tenant_security),
) -> Generator[Session, None, None]:
    """Resolve the current tenant database from the tenant-scoped JWT."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("scope") != "tenant":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant token is required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_slug = payload.get("tenant_slug")
    if not tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant token missing tenant_slug",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with tenant_db_session_by_slug(tenant_slug) as (tenant_db, _):
        yield tenant_db
