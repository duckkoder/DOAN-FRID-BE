"""add platform audit logs

Revision ID: platform_audit_logs
Revises: 17f0aae5f9d8
Create Date: 2026-06-01 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "platform_audit_logs"
down_revision: Union[str, None] = "17f0aae5f9d8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "platform_audit_logs",
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_email", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("tenant_school_code", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["platform_users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_platform_audit_logs_action"), "platform_audit_logs", ["action"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_actor_email"), "platform_audit_logs", ["actor_email"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_actor_id"), "platform_audit_logs", ["actor_id"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_id"), "platform_audit_logs", ["id"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_status"), "platform_audit_logs", ["status"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_tenant_id"), "platform_audit_logs", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_platform_audit_logs_tenant_school_code"), "platform_audit_logs", ["tenant_school_code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_platform_audit_logs_tenant_school_code"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_tenant_id"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_status"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_id"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_actor_id"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_actor_email"), table_name="platform_audit_logs")
    op.drop_index(op.f("ix_platform_audit_logs_action"), table_name="platform_audit_logs")
    op.drop_table("platform_audit_logs")
