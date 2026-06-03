"""Read-only tenant database schema inspection."""
import psycopg2

from app.core.crypto import decrypt_secret
from app.platform.models.tenant import Tenant
from app.platform.schemas import TenantDbSchemaResponse, TenantDbTableInfo
from app.platform.services.tenant_service import get_tenant_or_404


class TenantDbSchemaService:
    """Expose tenant DB structure without reading tenant table data."""

    @staticmethod
    def inspect_tenant(tenant_id: int, platform_db) -> TenantDbSchemaResponse:
        tenant: Tenant = get_tenant_or_404(platform_db, tenant_id)
        conn = psycopg2.connect(
            dbname=tenant.db_name,
            user=tenant.db_user,
            password=decrypt_secret(tenant.db_password_encrypted),
            host=tenant.db_host,
            port=tenant.db_port,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        t.table_name,
                        t.table_type,
                        COUNT(c.column_name)::int AS column_count
                    FROM information_schema.tables t
                    LEFT JOIN information_schema.columns c
                        ON c.table_schema = t.table_schema
                        AND c.table_name = t.table_name
                    WHERE t.table_schema = 'public'
                    GROUP BY t.table_name, t.table_type
                    ORDER BY t.table_name
                    """
                )
                tables = [
                    TenantDbTableInfo(
                        table_name=row[0],
                        table_type=row[1],
                        column_count=row[2],
                    )
                    for row in cur.fetchall()
                ]

                cur.execute("SELECT to_regclass('public.alembic_version')")
                has_alembic = cur.fetchone()[0] is not None
                alembic_version = None
                if has_alembic:
                    cur.execute("SELECT version_num FROM public.alembic_version LIMIT 1")
                    row = cur.fetchone()
                    alembic_version = row[0] if row else None

        finally:
            conn.close()

        return TenantDbSchemaResponse(
            tenant_id=tenant.id,
            name=tenant.name,
            school_code=tenant.school_code,
            db_name=tenant.db_name,
            db_host=tenant.db_host,
            db_port=tenant.db_port,
            alembic_version=alembic_version,
            has_tenant_settings=any(table.table_name == "tenant_settings" for table in tables),
            table_count=len(tables),
            tables=tables,
        )
