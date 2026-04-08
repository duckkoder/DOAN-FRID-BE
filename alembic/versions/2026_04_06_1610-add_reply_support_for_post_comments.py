"""add_reply_support_for_post_comments

Revision ID: add_comment_reply_support
Revises: add_post_react_comment
Create Date: 2026-04-06 16:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "add_comment_reply_support"
down_revision: Union[str, None] = "add_post_react_comment"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("post_comments", sa.Column("parent_comment_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_post_comments_parent_comment_id",
        "post_comments",
        "post_comments",
        ["parent_comment_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_post_comments_parent_comment_id", "post_comments", ["parent_comment_id"], unique=False)
    op.create_index("ix_post_comments_parent_created_at", "post_comments", ["parent_comment_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_post_comments_parent_created_at", table_name="post_comments")
    op.drop_index("ix_post_comments_parent_comment_id", table_name="post_comments")
    op.drop_constraint("fk_post_comments_parent_comment_id", "post_comments", type_="foreignkey")
    op.drop_column("post_comments", "parent_comment_id")
