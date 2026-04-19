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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
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

    # 3. Create chat_sessions table (chưa có trong chuỗi migration cũ)
    op.create_table(
        'chat_sessions',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('course_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['course_id'], ['courses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_sessions_student_id', 'chat_sessions', ['student_id'])
    op.create_index('ix_chat_sessions_course_id', 'chat_sessions', ['course_id'])

    # 4. Create chat_messages table (chưa có trong chuỗi migration cũ)
    op.create_table(
        'chat_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('session_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('role', sa.Enum('user', 'ai', name='chat_role_enum'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['chat_sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_chat_messages_session_id', 'chat_messages', ['session_id'])

    # 5. Add chunk_index column to document_chunks (nếu chưa có)
    op.add_column('document_chunks', sa.Column('chunk_index', sa.Integer(), nullable=True))

    # 6. Add Foreign Key constraints to existing documents table
    # Fix any orphaned documents by creating dummy courses first
    op.execute(
        """
        INSERT INTO courses (id, code, title, description, created_at)
        SELECT DISTINCT course_id, 'MIGRATED_' || SUBSTRING(course_id::text, 1, 8), 'Migrated Course ' || SUBSTRING(course_id::text, 1, 8), 'Auto-generated during migration', NOW()
        FROM documents
        WHERE course_id NOT IN (SELECT id FROM courses)
        """
    )
    
    # Do the same for chat_sessions if any existed
    op.execute(
        """
        INSERT INTO courses (id, code, title, description, created_at)
        SELECT DISTINCT course_id, 'MIGRATED_' || SUBSTRING(course_id::text, 1, 8), 'Migrated Course ' || SUBSTRING(course_id::text, 1, 8), 'Auto-generated during migration', NOW()
        FROM chat_sessions
        WHERE course_id NOT IN (SELECT id FROM courses)
        """
    )
    op.create_foreign_key(
        'fk_documents_course_id_courses', 'documents', 'courses',
        ['course_id'], ['id'], ondelete='CASCADE'
    )

    # 7. Create GIN index for fuzzy search on document_chunks
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
