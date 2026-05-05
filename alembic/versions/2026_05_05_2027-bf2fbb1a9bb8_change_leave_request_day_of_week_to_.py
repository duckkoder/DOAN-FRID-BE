"""change_leave_request_day_of_week_to_integer

Revision ID: bf2fbb1a9bb8
Revises: d0b43e2746d0
Create Date: 2026-05-05 20:27:12.946981

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf2fbb1a9bb8'
down_revision: Union[str, None] = 'd0b43e2746d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Delete old rows with non-numeric day_of_week strings (e.g. "Monday")
    # so the USING cast won't fail on non-numeric values
    op.execute("DELETE FROM leave_requests WHERE day_of_week !~ '^[0-9]+$'")
    # Cast varchar to integer using USING clause (required by PostgreSQL)
    op.execute("""
        ALTER TABLE leave_requests
        ALTER COLUMN day_of_week TYPE INTEGER
        USING day_of_week::integer
    """)


def downgrade() -> None:
    op.alter_column('leave_requests', 'day_of_week',
               existing_type=sa.Integer(),
               type_=sa.VARCHAR(length=20),
               existing_nullable=False)
