"""merge file and class schema branches

Revision ID: 47f847b0dc1d
Revises: bb1a342bae35, 539d99202600
Create Date: 2025-10-28 09:39:17.226523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '47f847b0dc1d'
down_revision: Union[str, None] = ('bb1a342bae35', '539d99202600')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
