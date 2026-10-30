import asyncio
import logging
from typing import Callable, List, Optional
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from models.db import Chunk as ChunkDB
from models.enums import ProcessingStatus
from retrieval.embedding import BGEEmbeddingService

logger = logging.getLogger(__name__)


class EmbeddingWorker:
    """
    Safe concurrent/asynchronous embedding worker.
    
    Responsibilities:
    - Finds pending chunks (`processing_status == PENDING`).
    - Applies atomic row locking (PostgreSQL `FOR UPDATE SKIP LOCKED`) to avoid race conditions.
    - Checks for duplicate chunk content hashes within the tenant to reuse existing embeddings.
    - Generates dense BGE embeddings in batches.
    - Updates chunks to `COMPLETED` or `FAILED` on exception.
    - Strictly preserves organization-level tenant boundaries.
    
    Time Complexity:
    - O(B * L) per batch of size B with sequence token length L.
    """

    def __init__(
        self,
        embedding_service: Optional[BGEEmbeddingService] = None,
        model_name: str = "BAAI/bge-small-en-v1.5",
    ):
        """
        Initialize the embedding worker.

        Args:
            embedding_service: Optional pre-configured BGEEmbeddingService instance.
            model_name: Model identifier to verify and record against chunks.
        """
        self.embedding_service = embedding_service or BGEEmbeddingService(model_name=model_name)
        self.model_name = model_name

    def process_batch(
        self,
        session: Session,
        batch_size: int = 32,
        organization_id: Optional[UUID] = None,
    ) -> int:
        """
        Process a single batch of pending chunks atomically.

        Args:
            session: Active SQLAlchemy Session.
            batch_size: Number of pending chunks to process in this batch.
            organization_id: Optional tenant filter to isolate worker to a single tenant.

        Returns:
            Number of chunks successfully processed in this batch.
        """
        stmt = (
            select(ChunkDB)
            .where(
                ChunkDB.processing_status == ProcessingStatus.PENDING,
                ChunkDB.embedding_model == self.model_name,
            )
            .order_by(ChunkDB.chunk_id)
            .limit(batch_size)
        )

        if organization_id is not None:
            stmt = stmt.where(ChunkDB.organization_id == organization_id)

        # Apply FOR UPDATE SKIP LOCKED if dialect is PostgreSQL
        bind = session.get_bind()
        if bind and bind.dialect.name == "postgresql":
            stmt = stmt.with_for_update(skip_locked=True)

        pending_chunks: List[ChunkDB] = list(session.scalars(stmt).all())
        if not pending_chunks:
            return 0

        # Mark chunks as processing
        chunk_ids = [c.chunk_id for c in pending_chunks]
        for c in pending_chunks:
            c.processing_status = ProcessingStatus.PROCESSING
        session.flush()

        try:
            chunks_needing_inference: List[ChunkDB] = []
            texts_to_embed: List[str] = []

            # Deduplication check: check if identical chunk_hash already has an embedding
            for chunk in pending_chunks:
                # Query within the same tenant to preserve isolation
                cached_chunk = session.scalar(
                    select(ChunkDB)
                    .where(
                        ChunkDB.organization_id == chunk.organization_id,
                        ChunkDB.chunk_hash == chunk.chunk_hash,
                        ChunkDB.embedding_model == self.model_name,
                        ChunkDB.embedding.is_not(None),
                        ChunkDB.processing_status == ProcessingStatus.COMPLETED,
                    )
                    .limit(1)
                )

                if cached_chunk and cached_chunk.embedding is not None:
                    # Reuse existing embedding directly without inference
                    chunk.embedding = list(cached_chunk.embedding)
                    chunk.processing_status = ProcessingStatus.COMPLETED
                    logger.debug(
                        "Reused precomputed embedding for chunk %s (hash=%s)",
                        chunk.chunk_id,
                        chunk.chunk_hash[:8],
                    )
                else:
                    chunks_needing_inference.append(chunk)
                    # Prepare text for embedding (incorporating context breadcrumbs)
                    if chunk.section_context and chunk.section_context.strip():
                        enriched_text = f"{chunk.section_context}\n\n{chunk.content}"
                    else:
                        enriched_text = chunk.content
                    texts_to_embed.append(enriched_text)

            # Perform batch inference for remaining chunks
            if chunks_needing_inference:
                embeddings = self.embedding_service.embed_documents(
                    texts_to_embed, batch_size=batch_size
                )

                for chunk, emb in zip(chunks_needing_inference, embeddings):
                    chunk.embedding = emb
                    chunk.processing_status = ProcessingStatus.COMPLETED

            session.commit()
            logger.info("Successfully processed embedding batch of %d chunks.", len(pending_chunks))
            return len(pending_chunks)

        except Exception as e:
            session.rollback()
            logger.exception("Failed processing embedding batch for chunk IDs %s: %s", chunk_ids, e)
            # Mark chunks as failed in a new transaction
            try:
                session.execute(
                    update(ChunkDB)
                    .where(ChunkDB.chunk_id.in_(chunk_ids))
                    .values(processing_status=ProcessingStatus.FAILED)
                )
                session.commit()
            except Exception as mark_err:
                session.rollback()
                logger.error("Failed marking chunks as FAILED: %s", mark_err)
            raise e

    def process_all_pending(
        self,
        session_factory: Callable[[], Session],
        batch_size: int = 32,
        organization_id: Optional[UUID] = None,
        max_batches: Optional[int] = None,
    ) -> int:
        """
        Drain all pending chunks across batches.

        Args:
            session_factory: Factory function yielding new SQLAlchemy sessions.
            batch_size: Batch size per iteration.
            organization_id: Optional tenant isolation filter.
            max_batches: Optional cap on iterations (useful for test harness or rate limits).

        Returns:
            Total count of processed chunks.
        """
        total_processed = 0
        batches = 0

        while True:
            if max_batches is not None and batches >= max_batches:
                break

            with session_factory() as session:
                count = self.process_batch(
                    session=session,
                    batch_size=batch_size,
                    organization_id=organization_id,
                )
                if count == 0:
                    break
                total_processed += count
                batches += 1

        return total_processed

    async def run_worker_loop(
        self,
        session_factory: Callable[[], Session],
        poll_interval: float = 2.0,
        batch_size: int = 32,
        organization_id: Optional[UUID] = None,
        stop_event: Optional[asyncio.Event] = None,
    ):
        """
        Asynchronous worker loop continuously polling for pending chunks.

        Args:
            session_factory: SQLAlchemy session factory.
            poll_interval: Sleep interval in seconds when no pending items are found.
            batch_size: Batch size for each execution.
            organization_id: Optional organization tenant boundary.
            stop_event: Optional asyncio Event to cleanly stop the worker loop.
        """
        logger.info("Starting EmbeddingWorker background polling loop...")
        while stop_event is None or not stop_event.is_set():
            try:
                with session_factory() as session:
                    processed = self.process_batch(
                        session=session,
                        batch_size=batch_size,
                        organization_id=organization_id,
                    )
                if processed == 0:
                    await asyncio.sleep(poll_interval)
            except asyncio.CancelledError:
                logger.info("EmbeddingWorker received cancellation signal.")
                break
            except Exception as e:
                logger.error("Error in EmbeddingWorker loop: %s", e)
                await asyncio.sleep(poll_interval)
