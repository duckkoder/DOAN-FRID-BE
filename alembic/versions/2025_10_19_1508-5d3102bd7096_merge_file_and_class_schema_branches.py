"""Merge file and class schema branches

Revision ID: 5d3102bd7096
Revises: 4ece829d0428, 61c9b47de1e9
Create Date: 2025-10-19 15:08:08.497355

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5d3102bd7096'
down_revision: Union[str, None] = ('4ece829d0428', '61c9b47de1e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
