"""create_spoof_detections_table

Revision ID: create_spoof_detections
Revises: 096dc9e4aeea
Create Date: 2026-01-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'create_spoof_detections'
down_revision: Union[str, None] = '096dc9e4aeea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create spoof_detections table
    op.create_table(
        'spoof_detections',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('spoofing_type', sa.String(length=50), nullable=False, comment="Type of spoofing detected: 'spoof', 'print', 'replay', 'mask', etc."),
        sa.Column('spoofing_confidence', sa.Float(), nullable=False, comment='Confidence score of spoofing detection (0.0 - 1.0)'),
        sa.Column('image_path', sa.String(length=255), nullable=True, comment='S3 presigned URL to spoof face image'),
        sa.Column('detected_at', sa.DateTime(timezone=True), nullable=True, comment='Timestamp when spoofing was detected'),
        sa.Column('frame_count', sa.Integer(), nullable=True, comment='Frame number in which spoofing was detected'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.ForeignKeyConstraint(['session_id'], ['attendance_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes
    op.create_index('ix_spoof_detection_session_id', 'spoof_detections', ['session_id'], unique=False)
    op.create_index('ix_spoof_detection_detected_at', 'spoof_detections', ['detected_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_spoof_detection_detected_at', table_name='spoof_detections')
    op.drop_index('ix_spoof_detection_session_id', table_name='spoof_detections')
    
    # Drop table
    op.drop_table('spoof_detections')
