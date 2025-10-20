"""merge file and class schema changes

Revision ID: 2234b4c274f1
Revises: 4ece829d0428, 61c9b47de1e9
Create Date: 2025-10-15 14:57:43.638083

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2234b4c274f1'
down_revision: Union[str, None] = ('4ece829d0428', '61c9b47de1e9')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
