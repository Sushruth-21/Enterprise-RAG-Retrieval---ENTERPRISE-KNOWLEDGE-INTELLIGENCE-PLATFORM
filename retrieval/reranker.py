import logging
import math
from typing import List, Optional
import numpy as np

from retrieval.models import SearchResult

logger = logging.getLogger(__name__)

DEFAULT_BGE_RERANKER = "BAAI/bge-reranker-base"


def _sigmoid(x: float) -> float:
    """Compute numerical-stable sigmoid."""
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    else:
        z = math.exp(x)
        return z / (1.0 + z)


class BGEReranker:
    """
    Cross-Encoder Reranker using BAAI/bge-reranker-base.
    
    Responsibilities:
    - Takes candidate SearchResult items from hybrid retrieval.
    - Evaluates query-document cross-attention pairs.
    - Converts raw logits to normalized confidence scores in [0.0, 1.0].
    - Ranks and returns top-K candidates.
    
    Time Complexity:
    - O(C * (L_q + L_d)) where C is the number of candidates and L_q, L_d are token lengths.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_BGE_RERANKER,
        max_length: int = 512,
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize the BGE reranker.

        Args:
            model_name: Model identifier (e.g. 'BAAI/bge-reranker-base').
            max_length: Max token length for query + document pair.
            cache_dir: Custom cache directory for model weights.
        """
        self.model_name = model_name
        self.max_length = max_length
        self.cache_dir = cache_dir
        self._model = None

    def _load_model(self):
        """Lazy loader for the cross-encoder reranker model."""
        if self._model is not None:
            return self._model

        try:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            logger.info("Loading BGE reranker '%s' via fastembed ONNX runtime...", self.model_name)
            self._model = TextCrossEncoder(
                model_name=self.model_name,
                max_length=self.max_length,
                cache_dir=self.cache_dir,
            )
            return self._model
        except Exception as e:
            logger.warning("Fastembed reranker loading failed: %s. Trying sentence_transformers...", e)
            try:
                from sentence_transformers import CrossEncoder
                self._model = CrossEncoder(self.model_name)
                return self._model
            except Exception as st_err:
                raise RuntimeError(
                    f"Failed to initialize BGE reranker '{self.model_name}': {e}; {st_err}"
                )

    def rerank(
        self,
        query: str,
        candidates: List[SearchResult],
        top_k: Optional[int] = None,
        batch_size: int = 16,
    ) -> List[SearchResult]:
        """
        Rerank candidate SearchResult items using the cross-encoder.

        Args:
            query: User query string.
            candidates: List of retrieved candidates from vector/fulltext/hybrid search.
            top_k: Max number of top reranked items to return (defaults to all).
            batch_size: Batch size for cross-encoder inference.

        Returns:
            List of SearchResult items ordered descending by cross-encoder score.
        """
        if not candidates or not query or not query.strip():
            return candidates[:top_k] if top_k else candidates

        model = self._load_model()
        passages = [f"{c.section_context}\n{c.content}" if c.section_context else c.content for c in candidates]

        # Fastembed path
        if hasattr(model, "rerank"):
            scores_gen = model.rerank(query=query, documents=passages, batch_size=batch_size)
            raw_scores = list(scores_gen)
        else:
            # SentenceTransformers CrossEncoder path
            pairs = [[query, p] for p in passages]
            raw_scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)

        # Convert scores to normalized float probabilities
        normalized_scores = [_sigmoid(float(s)) for s in raw_scores]

        # Pair candidates with their scores
        scored_candidates = []
        for cand, score in zip(candidates, normalized_scores):
            # Create a copy with updated score and source method
            item = cand.model_copy()
            item.score = score
            item.source_method = "reranked"
            item.metadata = {**cand.metadata, "cross_encoder_score": score}
            scored_candidates.append(item)

        # Sort descending by rerank score
        scored_candidates.sort(key=lambda x: x.score, reverse=True)

        # Update ranks
        reranked_results = []
        for rank, item in enumerate(scored_candidates[:top_k], start=1):
            item.rank = rank
            reranked_results.append(item)

        return reranked_results
