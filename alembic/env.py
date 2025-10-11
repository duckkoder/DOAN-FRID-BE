from logging.config import fileConfig
from sqlalchemy import engine_from_config, create_engine
from sqlalchemy import pool
from alembic import context
import os

# ✅ Force load .env
from dotenv import load_dotenv
env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(env_path, override=True)

# ✅ Import settings và models
from app.core.config import settings
from app.models.base import Base
from app.models.test import Test

# Alembic Config object
config = context.config

# ✅ Debug output
print("=" * 60)
print("🔍 Alembic Environment")
print("=" * 60)
print(f"📊 DATABASE_URL: {settings.DATABASE_URL[:50]}...")
print("=" * 60)

# Interpret logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set target metadata
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    # ✅ Dùng trực tiếp DATABASE_URL từ settings
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    # ✅ Tạo engine trực tiếp từ settings (không qua alembic.ini)
    connectable = create_engine(
        settings.DATABASE_URL,
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()