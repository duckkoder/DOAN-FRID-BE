"""Provision tenant databases and run tenant migrations."""
import os
import re
import subprocess
import sys

import psycopg2
from psycopg2 import sql
from fastapi import HTTPException, status
from sqlalchemy.engine import URL, make_url

from app.core.config import settings
from app.core.crypto import decrypt_secret
from app.platform.models.tenant import Tenant


_DB_NAME_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]{0,62}$")


def validate_database_name(db_name: str) -> None:
    if not _DB_NAME_RE.match(db_name):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Database name must start with a letter/underscore and contain only letters, numbers, underscores",
        )


def build_tenant_database_url(tenant: Tenant) -> str:
    url = URL.create(
        "postgresql",
        username=tenant.db_user,
        password=decrypt_secret(tenant.db_password_encrypted),
        host=tenant.db_host,
        port=tenant.db_port,
        database=tenant.db_name,
    )
    return url.render_as_string(hide_password=False)


def create_tenant_database(tenant: Tenant) -> None:
    """Create a tenant PostgreSQL database if it does not exist."""
    validate_database_name(tenant.db_name)
    platform_url = make_url(settings.PLATFORM_DATABASE_URL)
    maintenance_db = platform_url.database or "postgres"
    admin_db = "postgres" if maintenance_db == tenant.db_name else maintenance_db

    conn = psycopg2.connect(
        dbname=admin_db,
        user=platform_url.username,
        password=platform_url.password,
        host=platform_url.host,
        port=platform_url.port,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (tenant.db_user,))
            tenant_password = decrypt_secret(tenant.db_password_encrypted)
            if not cur.fetchone():
                cur.execute(
                    sql.SQL("CREATE ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(tenant.db_user)
                    ),
                    (tenant_password,),
                )
            else:
                cur.execute(
                    sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD %s").format(
                        sql.Identifier(tenant.db_user)
                    ),
                    (tenant_password,),
                )

            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (tenant.db_name,))
            if cur.fetchone():
                cur.execute(
                    sql.SQL("ALTER DATABASE {} OWNER TO {}").format(
                        sql.Identifier(tenant.db_name),
                        sql.Identifier(tenant.db_user),
                    )
                )
                return
            cur.execute(
                sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    sql.Identifier(tenant.db_name),
                    sql.Identifier(tenant.db_user),
                )
            )
    finally:
        conn.close()


def ensure_tenant_extensions(tenant: Tenant) -> None:
    """Create privileged PostgreSQL extensions before tenant-user migrations run."""
    platform_url = make_url(settings.PLATFORM_DATABASE_URL)
    conn = psycopg2.connect(
        dbname=tenant.db_name,
        user=platform_url.username,
        password=platform_url.password,
        host=tenant.db_host,
        port=tenant.db_port,
    )
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
    finally:
        conn.close()


def run_tenant_migrations(tenant: Tenant) -> None:
    """Run Alembic migrations against a tenant database."""
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = build_tenant_database_url(tenant)
    env["PYTHONIOENCODING"] = "utf-8"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Tenant migration failed: {result.stderr or result.stdout}",
        )
