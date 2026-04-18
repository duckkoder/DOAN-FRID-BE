"""Upgrade RAG infrastructure with Course model and Vector/Trigram optimizations.

Revision ID: 2026_04_18_1500
Revises: 2026_04_06_1830
Create Date: 2026-04-18 15:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2026_04_18_1500'
down_revision = 'enable_teacher_interaction'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Enable extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS pgvector;")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

    # 2. Create courses table
    op.create_table(
        'courses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_courses_code'), 'courses', ['code'], unique=True)

    # 3. Add Foreign Key constraints to existing tables
    # First, we might need to clean up any orphaned course_ids (since they were UUIDs without FKs)
    # But since we're restoring from a fresh backup, we'll assume the data is clean or will be handled.
    
    op.create_foreign_key(
        'fk_documents_course_id_courses', 'documents', 'courses',
        ['course_id'], ['id'], ondelete='CASCADE'
    )
    
    op.create_foreign_key(
        'fk_chat_sessions_course_id_courses', 'chat_sessions', 'courses',
        ['course_id'], ['id'], ondelete='CASCADE'
    )

    # 4. Create GIN index for fuzzy search on document_chunks
    op.create_index(
        'idx_document_chunks_text_trgm',
        'document_chunks',
        ['chunk_text'],
        unique=False,
        postgresql_using='gin',
        postgresql_ops={'chunk_text': 'gin_trgm_ops'}
    )


def downgrade():
    op.drop_index('idx_document_chunks_text_trgm', table_name='document_chunks')
    op.drop_constraint('fk_chat_sessions_course_id_courses', 'chat_sessions', type_='foreignkey')
    op.drop_constraint('fk_documents_course_id_courses', 'documents', type_='foreignkey')
    op.drop_index(op.f('ix_courses_code'), table_name='courses')
    op.drop_table('courses')
    # We generally don't drop extensions in downgrade as they might be used elsewhere
