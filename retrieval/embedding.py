import logging
from typing import List, Optional, Union
import numpy as np

logger = logging.getLogger(__name__)

DEFAULT_BGE_MODEL = "BAAI/bge-small-en-v1.5"
DEFAULT_BGE_DIMENSION = 384
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class BGEEmbeddingService:
    """
    Embedding service for generating dense vector embeddings using BAAI BGE models.
    
    Supports:
    - Document embedding (raw text).
    - Query embedding (with BGE instruction prefix: 'Represent this sentence for searching relevant passages: ').
    - Vector normalization (L2) for cosine similarity via inner product.
    - High-throughput batch processing via ONNX Runtime (fastembed) with graceful fallbacks.
    
    Time Complexity:
    - O(N * L) where N is the number of text items and L is the sequence token length.
    """

    def __init__(
        self,
        model_name: str = DEFAULT_BGE_MODEL,
        max_length: int = 512,
        normalize_embeddings: bool = True,
        cache_dir: Optional[str] = None,
    ):
        """
        Initialize the BGE embedding service.

        Args:
            model_name: Name of the BGE model (e.g. 'BAAI/bge-small-en-v1.5').
            max_length: Maximum sequence length for tokenization (defaults to 512).
            normalize_embeddings: Whether to L2-normalize output embeddings.
            cache_dir: Optional custom model download and cache directory.
        """
        self.model_name = model_name
        self.max_length = max_length
        self.normalize_embeddings = normalize_embeddings
        self.cache_dir = cache_dir
        self._model = None
        self._dimension: Optional[int] = None

    def _load_model(self):
        """Lazy loader for the embedding model."""
        if self._model is not None:
            return self._model

        try:
            from fastembed import TextEmbedding
            logger.info("Loading BGE model '%s' via fastembed ONNX runtime...", self.model_name)
            self._model = TextEmbedding(
                model_name=self.model_name,
                max_length=self.max_length,
                cache_dir=self.cache_dir,
            )
            # Determine dimension from model description or sample embedding
            sample = list(self._model.embed(["test"]))[0]
            self._dimension = len(sample)
            logger.info("Loaded '%s' with dimension %d", self.model_name, self._dimension)
            return self._model
        except Exception as e:
            logger.warning("Fastembed loading failed or not available: %s. Trying sentence_transformers...", e)
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer(self.model_name, cache_folder=self.cache_dir)
                self._dimension = self._model.get_sentence_embedding_dimension()
                return self._model
            except Exception as st_err:
                raise RuntimeError(
                    f"Failed to initialize BGE embedding model '{self.model_name}': {e}; {st_err}"
                )

    @property
    def dimension(self) -> int:
        """Returns the embedding vector dimension."""
        if self._dimension is None:
            self._load_model()
        return self._dimension or DEFAULT_BGE_DIMENSION

    def embed_documents(self, texts: List[str], batch_size: int = 32) -> List[List[float]]:
        """
        Generate dense vector embeddings for a list of document chunks.

        Note: Documents are embedded without the query instruction prefix.

        Args:
            texts: List of document chunk strings to embed.
            batch_size: Batch size for model inference.

        Returns:
            List of float embedding vectors (each length `self.dimension`).
        """
        if not texts:
            return []

        model = self._load_model()
        clean_texts = [t if t and t.strip() else " " for t in texts]

        # Fastembed path
        if hasattr(model, "embed"):
            embeddings_generator = model.embed(clean_texts, batch_size=batch_size)
            raw_embeddings = [np.array(e, dtype=np.float32) for e in embeddings_generator]
        else:
            # SentenceTransformer path
            raw = model.encode(
                clean_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                normalize_embeddings=self.normalize_embeddings,
            )
            raw_embeddings = [np.array(e, dtype=np.float32) for e in raw]

        if self.normalize_embeddings and hasattr(model, "embed"):
            normalized = []
            for vec in raw_embeddings:
                norm = np.linalg.norm(vec)
                if norm > 0:
                    normalized.append((vec / norm).tolist())
                else:
                    normalized.append(vec.tolist())
            return normalized

        return [vec.tolist() for vec in raw_embeddings]

    def embed_query(self, query: str) -> List[float]:
        """
        Generate dense vector embedding for a search query.

        Applies the standard BGE query instruction:
        'Represent this sentence for searching relevant passages: '

        Args:
            query: The user query string.

        Returns:
            A normalized float vector of length `self.dimension`.
        """
        if not query or not query.strip():
            raise ValueError("Query string cannot be empty.")

        # BGE models require query instruction prefix for asymmetric search
        prefixed_query = f"{BGE_QUERY_PREFIX}{query.strip()}"
        embeddings = self.embed_documents([prefixed_query], batch_size=1)
        return embeddings[0]

    def embed_single_document(self, text: str) -> List[float]:
        """Convenience method to embed a single document string."""
        return self.embed_documents([text], batch_size=1)[0]
