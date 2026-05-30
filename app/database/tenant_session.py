"""Tenant-aware database session helpers."""
from contextlib import contextmanager
from typing import Generator, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from app.core.crypto import decrypt_secret
from app.core.security import decode_token
from app.platform.database import PlatformSessionLocal
from app.platform.models.tenant import Tenant


_tenant_sessionmakers: dict[int, sessionmaker] = {}
tenant_security = HTTPBearer()


def _build_tenant_url(tenant: Tenant) -> URL:
    return URL.create(
        "postgresql",
        username=tenant.db_user,
        password=decrypt_secret(tenant.db_password_encrypted),
        host=tenant.db_host,
        port=tenant.db_port,
        database=tenant.db_name,
    )


def get_tenant_by_slug(slug: str, platform_db: Optional[Session] = None) -> Tenant:
    """Load an active tenant from the platform database."""
    owns_session = platform_db is None
    db = platform_db or PlatformSessionLocal()
    try:
        tenant = db.query(Tenant).filter(Tenant.slug == slug).first()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        if tenant.status != "active":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Tenant is suspended")
        return tenant
    finally:
        if owns_session:
            db.close()


def get_tenant_sessionmaker(tenant: Tenant) -> sessionmaker:
    """Return a cached sessionmaker for a tenant."""
    if tenant.id not in _tenant_sessionmakers:
        engine = create_engine(
            _build_tenant_url(tenant),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
            echo=False,
        )
        _tenant_sessionmakers[tenant.id] = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=engine,
        )
    return _tenant_sessionmakers[tenant.id]


def reset_tenant_sessionmaker(tenant_id: int) -> None:
    """Dispose and remove a cached tenant sessionmaker."""
    session_factory = _tenant_sessionmakers.pop(tenant_id, None)
    if session_factory is not None:
        bind = session_factory.kw.get("bind")
        if bind is not None:
            bind.dispose()


@contextmanager
def tenant_db_session_by_slug(slug: str):
    """Open a tenant DB session by tenant slug."""
    tenant = get_tenant_by_slug(slug)
    session_factory = get_tenant_sessionmaker(tenant)
    db = session_factory()
    try:
        yield db, tenant
    finally:
        db.close()


def get_tenant_db(
    credentials: HTTPAuthorizationCredentials = Depends(tenant_security),
) -> Generator[Session, None, None]:
    """FastAPI dependency that resolves tenant DB from JWT tenant_slug."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("scope") == "platform":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired tenant token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_slug = payload.get("tenant_slug")
    if not tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant token missing tenant_slug",
            headers={"WWW-Authenticate": "Bearer"},
        )

    with tenant_db_session_by_slug(tenant_slug) as (db, _):
        yield db


def get_current_tenant(
    credentials: HTTPAuthorizationCredentials = Depends(tenant_security),
) -> Tenant:
    """Resolve the current tenant from a tenant-scoped JWT."""
    payload = decode_token(credentials.credentials)
    if not payload or payload.get("scope") == "platform":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired tenant token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    tenant_slug = payload.get("tenant_slug")
    if not tenant_slug:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Tenant token missing tenant_slug",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return get_tenant_by_slug(tenant_slug)
