"""add_class_posts_documents_and_rag_chunks

Revision ID: add_class_posts_docs_chunks
Revises: create_spoof_detections
Create Date: 2026-04-06 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision: str = "add_class_posts_docs_chunks"
down_revision: Union[str, None] = "create_spoof_detections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "class_posts",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("class_id", sa.Integer(), nullable=False),
        sa.Column("teacher_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.ForeignKeyConstraint(["class_id"], ["classes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["teacher_id"], ["teachers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_class_posts_id", "class_posts", ["id"], unique=False)
    op.create_index("ix_class_posts_class_id", "class_posts", ["class_id"], unique=False)
    op.create_index("ix_class_posts_teacher_id", "class_posts", ["teacher_id"], unique=False)
    op.create_index("ix_class_posts_class_created_at", "class_posts", ["class_id", "created_at"], unique=False)

    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("file_url", sa.String(length=1000), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_documents_course_id", "documents", ["course_id"], unique=False)
    op.create_index("ix_documents_course_uploaded_at", "documents", ["course_id", "uploaded_at"], unique=False)

    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("chunk_text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim=768), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_document_chunks_document_id", "document_chunks", ["document_id"], unique=False)
    op.create_index("ix_document_chunks_document_page", "document_chunks", ["document_id", "page_number"], unique=False)
    op.create_index(
        "idx_document_chunks_embedding_hnsw",
        "document_chunks",
        ["embedding"],
        unique=False,
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )

    op.create_table(
        "post_attachments",
        sa.Column("post_id", sa.Integer(), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["post_id"], ["class_posts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("post_id", "document_id"),
    )
    op.create_index("ix_post_attachments_document_id", "post_attachments", ["document_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_post_attachments_document_id", table_name="post_attachments")
    op.drop_table("post_attachments")

    op.drop_index("idx_document_chunks_embedding_hnsw", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_page", table_name="document_chunks")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("ix_documents_course_uploaded_at", table_name="documents")
    op.drop_index("ix_documents_course_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("ix_class_posts_class_created_at", table_name="class_posts")
    op.drop_index("ix_class_posts_teacher_id", table_name="class_posts")
    op.drop_index("ix_class_posts_class_id", table_name="class_posts")
    op.drop_index("ix_class_posts_id", table_name="class_posts")
    op.drop_table("class_posts")
