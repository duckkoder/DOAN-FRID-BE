"""add_post_and_comment_mentions

Revision ID: add_post_comment_mentions
Revises: add_comment_reply_support
Create Date: 2026-04-06 17:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "add_post_comment_mentions"
down_revision: Union[str, None] = "add_comment_reply_support"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "post_document_mentions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_title", sa.String(length=255), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["class_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "document_id", name="uq_post_document_mention"),
    )
    op.create_index("ix_post_document_mentions_id", "post_document_mentions", ["id"], unique=False)
    op.create_index("ix_post_document_mentions_post_id", "post_document_mentions", ["post_id"], unique=False)
    op.create_index("ix_post_document_mentions_document_id", "post_document_mentions", ["document_id"], unique=False)
    op.create_index("ix_post_document_mentions_post_mentioned_at", "post_document_mentions", ["post_id", "mentioned_at"], unique=False)

    op.create_table(
        "post_member_mentions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("mentioned_name", sa.String(length=255), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["post_id"], ["class_posts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("post_id", "student_id", name="uq_post_member_mention"),
    )
    op.create_index("ix_post_member_mentions_id", "post_member_mentions", ["id"], unique=False)
    op.create_index("ix_post_member_mentions_post_id", "post_member_mentions", ["post_id"], unique=False)
    op.create_index("ix_post_member_mentions_student_id", "post_member_mentions", ["student_id"], unique=False)
    op.create_index("ix_post_member_mentions_post_mentioned_at", "post_member_mentions", ["post_id", "mentioned_at"], unique=False)

    op.create_table(
        "comment_document_mentions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_title", sa.String(length=255), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["comment_id"], ["post_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", "document_id", name="uq_comment_document_mention"),
    )
    op.create_index("ix_comment_document_mentions_id", "comment_document_mentions", ["id"], unique=False)
    op.create_index("ix_comment_document_mentions_comment_id", "comment_document_mentions", ["comment_id"], unique=False)
    op.create_index("ix_comment_document_mentions_document_id", "comment_document_mentions", ["document_id"], unique=False)
    op.create_index("ix_comment_document_mentions_comment_mentioned_at", "comment_document_mentions", ["comment_id", "mentioned_at"], unique=False)

    op.create_table(
        "comment_member_mentions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("comment_id", sa.Integer(), nullable=False),
        sa.Column("student_id", sa.Integer(), nullable=False),
        sa.Column("mentioned_name", sa.String(length=255), nullable=False),
        sa.Column("mentioned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["comment_id"], ["post_comments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_id"], ["students.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("comment_id", "student_id", name="uq_comment_member_mention"),
    )
    op.create_index("ix_comment_member_mentions_id", "comment_member_mentions", ["id"], unique=False)
    op.create_index("ix_comment_member_mentions_comment_id", "comment_member_mentions", ["comment_id"], unique=False)
    op.create_index("ix_comment_member_mentions_student_id", "comment_member_mentions", ["student_id"], unique=False)
    op.create_index("ix_comment_member_mentions_comment_mentioned_at", "comment_member_mentions", ["comment_id", "mentioned_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_comment_member_mentions_comment_mentioned_at", table_name="comment_member_mentions")
    op.drop_index("ix_comment_member_mentions_student_id", table_name="comment_member_mentions")
    op.drop_index("ix_comment_member_mentions_comment_id", table_name="comment_member_mentions")
    op.drop_index("ix_comment_member_mentions_id", table_name="comment_member_mentions")
    op.drop_table("comment_member_mentions")

    op.drop_index("ix_comment_document_mentions_comment_mentioned_at", table_name="comment_document_mentions")
    op.drop_index("ix_comment_document_mentions_document_id", table_name="comment_document_mentions")
    op.drop_index("ix_comment_document_mentions_comment_id", table_name="comment_document_mentions")
    op.drop_index("ix_comment_document_mentions_id", table_name="comment_document_mentions")
    op.drop_table("comment_document_mentions")

    op.drop_index("ix_post_member_mentions_post_mentioned_at", table_name="post_member_mentions")
    op.drop_index("ix_post_member_mentions_student_id", table_name="post_member_mentions")
    op.drop_index("ix_post_member_mentions_post_id", table_name="post_member_mentions")
    op.drop_index("ix_post_member_mentions_id", table_name="post_member_mentions")
    op.drop_table("post_member_mentions")

    op.drop_index("ix_post_document_mentions_post_mentioned_at", table_name="post_document_mentions")
    op.drop_index("ix_post_document_mentions_document_id", table_name="post_document_mentions")
    op.drop_index("ix_post_document_mentions_post_id", table_name="post_document_mentions")
    op.drop_index("ix_post_document_mentions_id", table_name="post_document_mentions")
    op.drop_table("post_document_mentions")
