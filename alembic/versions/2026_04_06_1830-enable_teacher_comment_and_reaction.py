"""enable_teacher_comment_and_reaction

Revision ID: enable_teacher_interaction
Revises: add_post_comment_mentions
Create Date: 2026-04-06 18:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "enable_teacher_interaction"
down_revision: Union[str, None] = "add_post_comment_mentions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("post_comments", sa.Column("teacher_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_post_comments_teacher_id",
        "post_comments",
        "teachers",
        ["teacher_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_post_comments_teacher_id", "post_comments", ["teacher_id"], unique=False)
    op.alter_column("post_comments", "student_id", existing_type=sa.Integer(), nullable=True)
    op.create_check_constraint(
        "ck_post_comments_actor",
        "post_comments",
        "((student_id IS NOT NULL AND teacher_id IS NULL) OR (student_id IS NULL AND teacher_id IS NOT NULL))",
    )

    op.add_column("post_reactions", sa.Column("teacher_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_post_reactions_teacher_id",
        "post_reactions",
        "teachers",
        ["teacher_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_post_reactions_teacher_id", "post_reactions", ["teacher_id"], unique=False)
    op.alter_column("post_reactions", "student_id", existing_type=sa.Integer(), nullable=True)

    op.drop_constraint("uq_post_reactions_post_student", "post_reactions", type_="unique")
    op.create_unique_constraint("uq_post_reactions_post_student_actor", "post_reactions", ["post_id", "student_id"])
    op.create_unique_constraint("uq_post_reactions_post_teacher_actor", "post_reactions", ["post_id", "teacher_id"])
    op.create_check_constraint(
        "ck_post_reactions_actor",
        "post_reactions",
        "((student_id IS NOT NULL AND teacher_id IS NULL) OR (student_id IS NULL AND teacher_id IS NOT NULL))",
    )


def downgrade() -> None:
    op.drop_constraint("ck_post_reactions_actor", "post_reactions", type_="check")
    op.drop_constraint("uq_post_reactions_post_teacher_actor", "post_reactions", type_="unique")
    op.drop_constraint("uq_post_reactions_post_student_actor", "post_reactions", type_="unique")
    op.create_unique_constraint("uq_post_reactions_post_student", "post_reactions", ["post_id", "student_id"])
    op.alter_column("post_reactions", "student_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_post_reactions_teacher_id", table_name="post_reactions")
    op.drop_constraint("fk_post_reactions_teacher_id", "post_reactions", type_="foreignkey")
    op.drop_column("post_reactions", "teacher_id")

    op.drop_constraint("ck_post_comments_actor", "post_comments", type_="check")
    op.alter_column("post_comments", "student_id", existing_type=sa.Integer(), nullable=False)
    op.drop_index("ix_post_comments_teacher_id", table_name="post_comments")
    op.drop_constraint("fk_post_comments_teacher_id", "post_comments", type_="foreignkey")
    op.drop_column("post_comments", "teacher_id")
