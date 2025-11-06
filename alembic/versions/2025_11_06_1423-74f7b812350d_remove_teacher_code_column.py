"""remove_teacher_code_column

Revision ID: 74f7b812350d
Revises: bcecc66ae7d0
Create Date: 2025-11-06 14:23:07.638202

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '74f7b812350d'
down_revision: Union[str, None] = 'bcecc66ae7d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop index first
    op.drop_index('ix_teachers_teacher_code', table_name='teachers')
    # Drop column
    op.drop_column('teachers', 'teacher_code')


def downgrade() -> None:
    # Add column back
    op.add_column('teachers', sa.Column('teacher_code', sa.String(length=20), nullable=False))
    # Recreate index
    op.create_index('ix_teachers_teacher_code', 'teachers', ['teacher_code'], unique=True)
