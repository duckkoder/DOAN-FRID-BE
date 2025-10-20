"""merge class schema and file table changes

Revision ID: 690a0af33322
Revises: 61c9b47de1e9, 4ece829d0428
Create Date: 2025-10-19 16:02:15.656812

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '690a0af33322'
down_revision: Union[str, None] = ('61c9b47de1e9', '4ece829d0428')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
