"""Migrate chat_sessions: replace student_id with user_id (FK to users.id).

Revision ID: a1b2c3d4e5f6
Revises: bf2fbb1a9bb8
Create Date: 2026-05-07 15:13:00
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = "a1b2c3d4e5f6"
down_revision = "bf2fbb1a9bb8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Drop old FK constraint and index on student_id
    op.drop_index("ix_chat_sessions_student_id", table_name="chat_sessions", if_exists=True)
    op.drop_constraint("chat_sessions_student_id_fkey", "chat_sessions", type_="foreignkey")

    # 2. Rename column student_id → user_id
    op.alter_column("chat_sessions", "student_id", new_column_name="user_id")

    # 3. Re-create FK pointing to users.id instead of students.id
    op.create_foreign_key(
        "chat_sessions_user_id_fkey",
        "chat_sessions", "users",
        ["user_id"], ["id"],
        ondelete="CASCADE",
    )

    # 4. Create composite index for fast lookup
    op.create_index("ix_chat_sessions_user_course", "chat_sessions", ["user_id", "course_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_sessions_user_course", table_name="chat_sessions")
    op.drop_constraint("chat_sessions_user_id_fkey", "chat_sessions", type_="foreignkey")
    op.alter_column("chat_sessions", "user_id", new_column_name="student_id")
    op.create_foreign_key(
        "chat_sessions_student_id_fkey",
        "chat_sessions", "students",
        ["student_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_chat_sessions_student_id", "chat_sessions", ["student_id"])
