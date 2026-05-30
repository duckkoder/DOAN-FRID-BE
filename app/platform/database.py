"""Platform database session management."""
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


platform_engine = create_engine(
    settings.PLATFORM_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    echo=False,
)

PlatformSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=platform_engine,
)


def get_platform_db() -> Generator[Session, None, None]:
    """Yield a platform database session."""
    db = PlatformSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_platform_db() -> None:
    """Create platform tables. Prefer migrations outside local setup scripts."""
    from app.platform.models import PlatformBase

    PlatformBase.metadata.create_all(bind=platform_engine)

