"""add_hnsw_vector_and_gin_fts_indexes_and_cache_lineage

Revision ID: 58e4cf27a6e1
Revises: 50f4f80b98af
Create Date: 2026-10-30 19:53:39.728771

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '58e4cf27a6e1'
down_revision: Union[str, Sequence[str], None] = '50f4f80b98af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with performance HNSW, GIN FTS indexes and cache lineage columns."""
    # 1. Add access_scope to chunks
    op.add_column('chunks', sa.Column('access_scope', sa.String(length=50), server_default='public', nullable=False))
    op.create_index('ix_chunks_access_scope', 'chunks', ['access_scope'], unique=False)

    # 2. Add lineage and security columns to qa_cache_entries
    op.add_column('qa_cache_entries', sa.Column('embedding_model', sa.String(length=100), server_default='BAAI/bge-small-en-v1.5', nullable=False))
    op.add_column('qa_cache_entries', sa.Column('llm_model', sa.String(length=100), nullable=True))
    op.add_column('qa_cache_entries', sa.Column('prompt_version', sa.String(length=50), nullable=True))
    op.add_column('qa_cache_entries', sa.Column('access_scope', sa.String(length=50), server_default='public', nullable=False))
    op.add_column('qa_cache_entries', sa.Column('user_id', sa.String(length=100), nullable=True))
    op.create_index('ix_qa_cache_entries_access_scope', 'qa_cache_entries', ['access_scope'], unique=False)
    op.create_index('ix_qa_cache_entries_user_id', 'qa_cache_entries', ['user_id'], unique=False)

    # 3. Add HNSW vector indexes for cosine similarity
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chunks_embedding_hnsw_cosine 
        ON chunks USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_qa_cache_query_embedding_hnsw_cosine 
        ON qa_cache_entries USING hnsw (query_embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64);
    """)

    # 4. Add GIN index matching actual PostgreSQL Full-Text Search query expressions
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_chunks_fts_gin 
        ON chunks USING gin (
            to_tsvector('english', coalesce(section_context, '') || ' ' || content)
        );
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_chunks_fts_gin;")
    op.execute("DROP INDEX IF EXISTS ix_qa_cache_query_embedding_hnsw_cosine;")
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw_cosine;")

    op.drop_index('ix_qa_cache_entries_user_id', table_name='qa_cache_entries')
    op.drop_index('ix_qa_cache_entries_access_scope', table_name='qa_cache_entries')
    op.drop_column('qa_cache_entries', 'user_id')
    op.drop_column('qa_cache_entries', 'access_scope')
    op.drop_column('qa_cache_entries', 'prompt_version')
    op.drop_column('qa_cache_entries', 'llm_model')
    op.drop_column('qa_cache_entries', 'embedding_model')

    op.drop_index('ix_chunks_access_scope', table_name='chunks')
    op.drop_column('chunks', 'access_scope')
