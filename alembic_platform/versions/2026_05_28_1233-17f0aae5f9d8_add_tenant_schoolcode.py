"""add tenant schoolcode

Revision ID: 17f0aae5f9d8
Revises: platform_initial
Create Date: 2026-05-28 12:33:44.069024
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



revision: str = '17f0aae5f9d8'
down_revision: Union[str, None] = 'platform_initial'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

