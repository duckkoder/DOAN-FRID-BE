"""add_timezone_to_datetime_columns

Revision ID: bcecc66ae7d0
Revises: e3a5a1e15f87
Create Date: 2025-11-04 21:38:10.935848

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bcecc66ae7d0'
down_revision: Union[str, None] = 'e3a5a1e15f87'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
