"""initial platform schema

Revision ID: platform_initial
Revises: 
Create Date: 2026-05-28 00:01:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "platform_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_users",
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_users_email"), "platform_users", ["email"], unique=True)
    op.create_index(op.f("ix_platform_users_id"), "platform_users", ["id"], unique=False)

    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("school_code", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("db_name", sa.String(length=255), nullable=False),
        sa.Column("db_host", sa.String(length=255), nullable=False),
        sa.Column("db_port", sa.Integer(), nullable=False),
        sa.Column("db_user", sa.String(length=255), nullable=False),
        sa.Column("db_password_encrypted", sa.String(length=1024), nullable=False),
        sa.Column("storage_provider", sa.String(length=50), nullable=False),
        sa.Column("storage_bucket", sa.String(length=255), nullable=True),
        sa.Column("storage_region", sa.String(length=100), nullable=True),
        sa.Column("storage_prefix", sa.String(length=255), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("school_code", name="uq_tenants_school_code"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index(op.f("ix_tenants_id"), "tenants", ["id"], unique=False)
    op.create_index(op.f("ix_tenants_school_code"), "tenants", ["school_code"], unique=False)
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_school_code"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_id"), table_name="tenants")
    op.drop_table("tenants")
    op.drop_index(op.f("ix_platform_users_id"), table_name="platform_users")
    op.drop_index(op.f("ix_platform_users_email"), table_name="platform_users")
    op.drop_table("platform_users")

