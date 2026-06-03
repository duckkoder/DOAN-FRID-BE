"""add tenant logo fields

Revision ID: add_tenant_logo
Revises: platform_audit_logs
Create Date: 2026-06-03 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "add_tenant_logo"
down_revision: Union[str, None] = "platform_audit_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("tenants", sa.Column("logo_key", sa.String(length=500), nullable=True))
    op.add_column("tenants", sa.Column("logo_url", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("tenants", "logo_url")
    op.drop_column("tenants", "logo_key")
