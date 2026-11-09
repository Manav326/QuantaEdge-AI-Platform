"""Initial curriculum knowledge schema.

Revision ID: 0001_knowledge
Revises:
"""
from alembic import op

from app.db import Base
from app import models  # noqa: F401

revision = "0001_knowledge"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=op.get_bind())
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
        "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
