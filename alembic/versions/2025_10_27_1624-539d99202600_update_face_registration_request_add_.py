"""update_face_registration_request_add_review_fields

Revision ID: 539d99202600
Revises: 3edd3e2de680
Create Date: 2025-10-27 16:24:38.421278

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '539d99202600'
down_revision: Union[str, None] = '3edd3e2de680'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename 'reviewed_at' to 'admin_reviewed_at'
    op.alter_column('face_registration_requests', 'reviewed_at',
                    new_column_name='admin_reviewed_at', existing_type=sa.DateTime())
    
    # Add new columns for student review
    op.add_column('face_registration_requests', sa.Column('student_reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('face_registration_requests', sa.Column('student_accepted', sa.Boolean(), nullable=True))
    
    # Add rejection_reason for admin
    op.add_column('face_registration_requests', sa.Column('rejection_reason', sa.Text(), nullable=True))
    
    # Add temp_images_data for storing preview images
    op.add_column('face_registration_requests', sa.Column('temp_images_data', sa.JSON(), nullable=True))
    
    # Update existing status values
    op.execute("""
        UPDATE face_registration_requests 
        SET status = CASE 
            WHEN status = 'pending' THEN 'collecting'
            WHEN status = 'processing' THEN 'collecting'
            WHEN status = 'completed' THEN 'approved'
            ELSE status
        END
    """)


def downgrade() -> None:
    # Remove new columns
    op.drop_column('face_registration_requests', 'temp_images_data')
    op.drop_column('face_registration_requests', 'rejection_reason')
    op.drop_column('face_registration_requests', 'student_accepted')
    op.drop_column('face_registration_requests', 'student_reviewed_at')
    
    # Rename back
    op.alter_column('face_registration_requests', 'admin_reviewed_at',
                    new_column_name='reviewed_at', existing_type=sa.DateTime())
    
    # Revert status values
    op.execute("""
        UPDATE face_registration_requests 
        SET status = CASE 
            WHEN status = 'collecting' THEN 'pending'
            WHEN status = 'approved' THEN 'completed'
            ELSE status
        END
    """)
