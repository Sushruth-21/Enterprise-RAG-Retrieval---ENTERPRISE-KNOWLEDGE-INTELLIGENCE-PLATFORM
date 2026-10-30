import logging
from typing import Optional

logger = logging.getLogger("document_intelligence.chunking.tokenizer")

_TIKTOKEN_ENCODER = None


def get_encoder():
    """Lazily load tiktoken encoder with fallback."""
    global _TIKTOKEN_ENCODER
    if _TIKTOKEN_ENCODER is None:
        try:
            import tiktoken
            # cl100k_base is standard for modern LLMs / embedding models
            _TIKTOKEN_ENCODER = tiktoken.get_encoding("cl100k_base")
        except Exception as e:
            logger.warning(f"Could not initialize tiktoken encoder ({e}); using character heuristic.")
            _TIKTOKEN_ENCODER = False
    return _TIKTOKEN_ENCODER


def count_tokens(text: str) -> int:
    """
    Counts the number of tokens in a string.
    Uses tiktoken cl100k_base if available; otherwise falls back to character estimation (~4 chars/token).
    """
    if not text:
        return 0

    encoder = get_encoder()
    if encoder:
        try:
            return len(encoder.encode(text, disallowed_special=()))
        except Exception:
            pass

    # Heuristic fallback: Average English word is ~4-5 characters, roughly 4 chars per token
    return max(1, len(text) // 4)
