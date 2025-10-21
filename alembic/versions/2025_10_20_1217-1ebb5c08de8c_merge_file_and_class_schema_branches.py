"""Merge file and class schema branches

Revision ID: 1ebb5c08de8c
Revises: 2234b4c274f1, 5d3102bd7096, 6c8385eb9848
Create Date: 2025-10-20 12:17:29.748154

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ebb5c08de8c'
down_revision: Union[str, None] = ('2234b4c274f1', '5d3102bd7096', '6c8385eb9848')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
