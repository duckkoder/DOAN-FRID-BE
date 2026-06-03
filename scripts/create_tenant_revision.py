"""Create an Alembic tenant migration from a template tenant database.

This is a dev/CI utility. It creates a revision file under alembic/versions,
then you review and commit that file before deploying to production.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from sqlalchemy.engine import URL, make_url


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import settings  # noqa: E402
from app.core.crypto import decrypt_secret  # noqa: E402


VERSIONS_DIR = PROJECT_ROOT / "alembic" / "versions"
DEFAULT_TEMPLATE_HOST = "localhost"
DEFAULT_TEMPLATE_PORT = 5432
DEFAULT_TEMPLATE_DB = "ai_attendance"
DEFAULT_TEMPLATE_USER = "postgres"
DEFAULT_TEMPLATE_PASSWORD = "Ttd02042004@"


def _build_default_template_url() -> str:
    return URL.create(
        "postgresql",
        username=DEFAULT_TEMPLATE_USER,
        password=DEFAULT_TEMPLATE_PASSWORD,
        host=DEFAULT_TEMPLATE_HOST,
        port=DEFAULT_TEMPLATE_PORT,
        database=DEFAULT_TEMPLATE_DB,
    ).render_as_string(hide_password=False)


def _build_template_url_from_tenant_code(tenant_code: str) -> str:
    platform_url = make_url(settings.PLATFORM_DATABASE_URL)
    conn = psycopg2.connect(
        dbname=platform_url.database,
        user=platform_url.username,
        password=platform_url.password,
        host=platform_url.host,
        port=platform_url.port,
    )
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT db_name, db_host, db_port, db_user, db_password_encrypted
                FROM tenants
                WHERE school_code = %s OR slug = %s
                LIMIT 1
                """,
                (tenant_code, tenant_code),
            )
            row = cur.fetchone()
            if not row:
                raise RuntimeError(f"Tenant template '{tenant_code}' not found in platform DB")

            db_name, db_host, db_port, db_user, encrypted_password = row
            return URL.create(
                "postgresql",
                username=db_user,
                password=decrypt_secret(encrypted_password),
                host=db_host,
                port=db_port,
                database=db_name,
            ).render_as_string(hide_password=False)
    finally:
        conn.close()


def _run_alembic(args: list[str], database_url: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["ALEMBIC_DATABASE_URL"] = database_url
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=PROJECT_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def _new_revision_files(before: set[str]) -> list[Path]:
    return sorted(
        [path for path in VERSIONS_DIR.glob("*.py") if path.name not in before],
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate a tenant Alembic revision using one template tenant DB.",
    )
    parser.add_argument("-m", "--message", required=True, help="Revision message, e.g. 'add tenant settings'")
    parser.add_argument(
        "--tenant-code",
        default=os.getenv("TENANT_TEMPLATE_SCHOOL_CODE"),
        help="Tenant school_code/slug used as template. Can also use TENANT_TEMPLATE_SCHOOL_CODE.",
    )
    parser.add_argument(
        "--database-url",
        default=os.getenv("TENANT_TEMPLATE_DATABASE_URL"),
        help="Template tenant DB URL. Overrides --tenant-code and hardcoded default template DB.",
    )
    parser.add_argument(
        "--upgrade-head-first",
        action="store_true",
        help="Run alembic upgrade head on the template DB before autogenerate.",
    )
    args = parser.parse_args()

    database_url = args.database_url
    if not database_url:
        if args.tenant_code:
            database_url = _build_template_url_from_tenant_code(args.tenant_code.strip().lower())
        else:
            database_url = _build_default_template_url()

    if args.upgrade_head_first:
        upgrade = _run_alembic(["upgrade", "head"], database_url)
        if upgrade.returncode != 0:
            print(upgrade.stdout, end="")
            print(upgrade.stderr, end="", file=sys.stderr)
            return upgrade.returncode

    before = {path.name for path in VERSIONS_DIR.glob("*.py")}
    result = _run_alembic(["revision", "--autogenerate", "-m", args.message.strip()], database_url)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    if result.returncode != 0:
        return result.returncode

    created = _new_revision_files(before)
    if not created:
        print("Alembic finished but no new revision file was detected.", file=sys.stderr)
        return 1

    print("\nCreated migration file:")
    for path in created:
        print(f"- {path.relative_to(PROJECT_ROOT)}")
    print("\nReview upgrade()/downgrade(), then commit this file before deploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
