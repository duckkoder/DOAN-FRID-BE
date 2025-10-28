"""merge multiple heads

Revision ID: d3b169b201ed
Revises: 6fed2c1112a6, a4798d1b28bf
Create Date: 2025-10-22 10:00:05.607713

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd3b169b201ed'
down_revision: Union[str, None] = ('6fed2c1112a6', 'a4798d1b28bf')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
