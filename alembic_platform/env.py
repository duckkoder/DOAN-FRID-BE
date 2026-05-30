from logging.config import fileConfig
import os

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import create_engine, pool

env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")
platform_env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env.platform")
load_dotenv(env_path, override=True)
load_dotenv(platform_env_path, override=True)

from app.core.config import settings  # noqa: E402
from app.platform.models import PlatformBase  # noqa: E402


config = context.config
database_url = os.getenv("PLATFORM_ALEMBIC_DATABASE_URL") or settings.PLATFORM_DATABASE_URL

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = PlatformBase.metadata


def run_migrations_offline():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(database_url, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

