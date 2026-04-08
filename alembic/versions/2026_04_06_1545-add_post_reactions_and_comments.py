"""add_post_reactions_and_comments

Revision ID: add_post_react_comment
Revises: add_class_posts_docs_chunks
Create Date: 2026-04-06 15:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_post_react_comment"
down_revision: Union[str, None] = "add_class_posts_docs_chunks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_reactions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("emoji", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["post_id"], ["class_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "student_id", name="uq_post_reactions_post_student"),
    )
    op.create_index("ix_post_reactions_id", "post_reactions", ["id"], unique=False)
    op.create_index("ix_post_reactions_post_id", "post_reactions", ["post_id"], unique=False)
    op.create_index("ix_post_reactions_student_id", "post_reactions", ["student_id"], unique=False)
    op.create_index("ix_post_reactions_post_emoji", "post_reactions", ["post_id", "emoji"], unique=False)

    op.create_table(
        "post_comments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["post_id"], ["class_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_post_comments_id", "post_comments", ["id"], unique=False)
    op.create_index("ix_post_comments_post_id", "post_comments", ["post_id"], unique=False)
    op.create_index("ix_post_comments_student_id", "post_comments", ["student_id"], unique=False)
    op.create_index("ix_post_comments_post_created_at", "post_comments", ["post_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_post_comments_post_created_at", table_name="post_comments")
    op.drop_index("ix_post_comments_student_id", table_name="post_comments")
    op.drop_index("ix_post_comments_post_id", table_name="post_comments")
    op.drop_index("ix_post_comments_id", table_name="post_comments")
    op.drop_table("post_comments")

    op.drop_index("ix_post_reactions_post_emoji", table_name="post_reactions")
    op.drop_index("ix_post_reactions_student_id", table_name="post_reactions")
    op.drop_index("ix_post_reactions_post_id", table_name="post_reactions")
    op.drop_index("ix_post_reactions_id", table_name="post_reactions")
    op.drop_table("post_reactions")
