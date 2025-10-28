"""merge two heads lqv and lvh

Revision ID: 8a3478de17f6
Revises: 6fed2c1112a6, a4798d1b28bf
Create Date: 2025-10-22 09:22:03.644004

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8a3478de17f6'
down_revision: Union[str, None] = ('6fed2c1112a6', 'a4798d1b28bf')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
