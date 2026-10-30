"""initial_schema_with_pgvector_and_qa_cache

Revision ID: 50f4f80b98af
Revises: 
Create Date: 2026-10-30 19:33:48.232046

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import pgvector
import pgvector.sqlalchemy


# revision identifiers, used by Alembic.
revision: str = '50f4f80b98af'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure pgvector extension is enabled
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    op.create_table('documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False, comment='Organization identifier for multi-tenant isolation'),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('canonical_id', sa.String(length=100), nullable=False, comment="Business/Domain entity identifier (e.g. 'CORP-HR-POL-042')"),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('status', sa.Enum('CURRENT', 'SUPERSEDED', name='documentstatus', native_enum=False), nullable=False),
    sa.Column('effective_date', sa.Date(), nullable=False),
    sa.Column('supersedes_id', sa.Uuid(), nullable=True, comment='Points to the prior version this document replaces'),
    sa.Column('file_uri', sa.String(length=1024), nullable=False, comment='S3/Blob storage path, URL, or local file reference'),
    sa.Column('file_hash', sa.String(length=64), nullable=False, comment='SHA-256 hash of original file to prevent duplicate uploads'),
    sa.Column('mime_type', sa.String(length=100), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['supersedes_id'], ['documents.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_doc_canonical_effective', 'documents', ['canonical_id', 'effective_date'], unique=False)
    op.create_index('ix_doc_org_canonical_status', 'documents', ['organization_id', 'canonical_id', 'status'], unique=False)
    op.create_index('ix_doc_org_file_hash', 'documents', ['organization_id', 'file_hash'], unique=False)
    op.create_index(op.f('ix_documents_canonical_id'), 'documents', ['canonical_id'], unique=False)
    op.create_index(op.f('ix_documents_effective_date'), 'documents', ['effective_date'], unique=False)
    op.create_index(op.f('ix_documents_file_hash'), 'documents', ['file_hash'], unique=False)
    op.create_index(op.f('ix_documents_name'), 'documents', ['name'], unique=False)
    op.create_index(op.f('ix_documents_organization_id'), 'documents', ['organization_id'], unique=False)
    op.create_index(op.f('ix_documents_status'), 'documents', ['status'], unique=False)
    op.create_table('qa_cache_entries',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False, comment='Tenant boundary for multi-tenant cache isolation'),
    sa.Column('query_text', sa.Text(), nullable=False, comment='Normalized original user question'),
    sa.Column('query_embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=False, comment='Dense vector embedding of query for semantic cache lookup'),
    sa.Column('answer_text', sa.Text(), nullable=False, comment='Cached answer text'),
    sa.Column('formatted_context', sa.Text(), nullable=False, comment='Synthesized grounding context provided to generator'),
    sa.Column('source_document_ids', sa.JSON(), nullable=False, comment='List of Document UUID strings the answer relies upon'),
    sa.Column('source_chunk_ids', sa.JSON(), nullable=False, comment='List of Chunk UUID strings the answer relies upon'),
    sa.Column('citation_metadata', sa.JSON(), nullable=True, comment='Structured citations (doc names, versions, page numbers, breadcrumbs)'),
    sa.Column('is_valid', sa.Boolean(), nullable=False, comment='Explicit invalidation flag (e.g. when source doc is superseded)'),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('last_accessed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_qa_cache_entries_is_valid'), 'qa_cache_entries', ['is_valid'], unique=False)
    op.create_index(op.f('ix_qa_cache_entries_organization_id'), 'qa_cache_entries', ['organization_id'], unique=False)
    op.create_index('ix_qa_cache_org_valid', 'qa_cache_entries', ['organization_id', 'is_valid'], unique=False)
    op.create_table('chunks',
    sa.Column('chunk_id', sa.Uuid(), nullable=False),
    sa.Column('organization_id', sa.Uuid(), nullable=False, comment='Tenant boundary for multi-tenant pgvector queries'),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('document_name', sa.String(length=255), nullable=False),
    sa.Column('version', sa.String(length=50), nullable=False),
    sa.Column('chunk_index', sa.Integer(), nullable=False, comment='Sequential order of the chunk within the document'),
    sa.Column('section_context', sa.Text(), nullable=False, comment="Structural heading breadcrumbs, e.g. '1.0 Introduction > 1.2 Scope'"),
    sa.Column('page_number', sa.Integer(), nullable=False),
    sa.Column('content', sa.Text(), nullable=False),
    sa.Column('chunk_hash', sa.String(length=64), nullable=False, comment='SHA-256 hash of chunk text for incremental embedding'),
    sa.Column('embedding_model', sa.String(length=100), nullable=False, comment='Embedding model identifier for incremental updates'),
    sa.Column('processing_status', sa.Enum('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED', name='processingstatus', native_enum=False), nullable=False, comment='Embedding processing status (pending, processing, completed, failed)'),
    sa.Column('document_status', sa.Enum('CURRENT', 'SUPERSEDED', name='documentstatus', native_enum=False), nullable=False, comment='Denormalized status for high-throughput vector/BM25 filtering'),
    sa.Column('embedding', pgvector.sqlalchemy.vector.VECTOR(dim=384), nullable=True, comment='Dense BGE vector embedding (384-dim) for semantic retrieval'),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('chunk_id')
    )
    op.create_index(op.f('ix_chunks_chunk_hash'), 'chunks', ['chunk_hash'], unique=False)
    op.create_index(op.f('ix_chunks_document_id'), 'chunks', ['document_id'], unique=False)
    op.create_index(op.f('ix_chunks_document_status'), 'chunks', ['document_status'], unique=False)
    op.create_index('ix_chunks_embedding_dedup', 'chunks', ['organization_id', 'chunk_hash', 'embedding_model'], unique=False)
    op.create_index('ix_chunks_order', 'chunks', ['document_id', 'chunk_index'], unique=False)
    op.create_index(op.f('ix_chunks_organization_id'), 'chunks', ['organization_id'], unique=False)
    op.create_index(op.f('ix_chunks_page_number'), 'chunks', ['page_number'], unique=False)
    op.create_index(op.f('ix_chunks_processing_status'), 'chunks', ['processing_status'], unique=False)
    op.create_index('ix_chunks_tenant_retrieval', 'chunks', ['organization_id', 'document_status', 'document_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index('ix_chunks_tenant_retrieval', table_name='chunks')
    op.drop_index(op.f('ix_chunks_processing_status'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_page_number'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_organization_id'), table_name='chunks')
    op.drop_index('ix_chunks_order', table_name='chunks')
    op.drop_index('ix_chunks_embedding_dedup', table_name='chunks')
    op.drop_index(op.f('ix_chunks_document_status'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_document_id'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_chunk_hash'), table_name='chunks')
    op.drop_table('chunks')
    op.drop_index('ix_qa_cache_org_valid', table_name='qa_cache_entries')
    op.drop_index(op.f('ix_qa_cache_entries_organization_id'), table_name='qa_cache_entries')
    op.drop_index(op.f('ix_qa_cache_entries_is_valid'), table_name='qa_cache_entries')
    op.drop_table('qa_cache_entries')
    op.drop_index(op.f('ix_documents_status'), table_name='documents')
    op.drop_index(op.f('ix_documents_organization_id'), table_name='documents')
    op.drop_index(op.f('ix_documents_name'), table_name='documents')
    op.drop_index(op.f('ix_documents_file_hash'), table_name='documents')
    op.drop_index(op.f('ix_documents_effective_date'), table_name='documents')
    op.drop_index(op.f('ix_documents_canonical_id'), table_name='documents')
    op.drop_index('ix_doc_org_file_hash', table_name='documents')
    op.drop_index('ix_doc_org_canonical_status', table_name='documents')
    op.drop_index('ix_doc_canonical_effective', table_name='documents')
    op.drop_table('documents')
    # ### end Alembic commands ###
