import logging
from typing import List, Optional, Set
import uuid

from retrieval.models import Citation, ContextResult, SearchResult

logger = logging.getLogger(__name__)


def _estimate_tokens(text: str) -> int:
    """Approximate token count using ~4 chars per token rule of thumb."""
    return max(1, len(text) // 4)


class ContextBuilder:
    """
    Context construction and citation extraction engine.
    
    Responsibilities:
    - Formats retrieved chunks into unambiguous prompt context blocks for downstream LLMs.
    - Generates complete citation metadata linking exact doc names, canonical IDs, versions,
      section breadcrumbs, page numbers, and text excerpts.
    - Strictly prevents inventing document content or hallucinated citations.
    - Enforces context window token and character budgets without splitting citation headers.
    
    Time Complexity:
    - O(K) where K is the number of retrieved search results.
    """

    def __init__(
        self,
        max_tokens: int = 3500,
        max_characters: Optional[int] = None,
        excerpt_length: int = 150,
    ):
        """
        Initialize the ContextBuilder.

        Args:
            max_tokens: Approximate token budget for formatted context.
            max_characters: Optional hard character budget cap.
            excerpt_length: Length of snippet excerpt stored in citation metadata.
        """
        self.max_tokens = max_tokens
        self.max_characters = max_characters or (max_tokens * 4)
        self.excerpt_length = excerpt_length

    def build_context(self, search_results: List[SearchResult]) -> ContextResult:
        """
        Assemble retrieved chunks into an LLM-ready context string with citation references.

        Args:
            search_results: Ranked list of SearchResult items.

        Returns:
            ContextResult containing formatted prompt text, structured citations, and stats.
        """
        if not search_results:
            return ContextResult(
                context_text="",
                citations=[],
                chunk_count=0,
                token_estimate=0,
                total_characters=0,
            )

        context_blocks: List[str] = []
        citations: List[Citation] = []
        seen_chunks: Set[uuid.UUID] = set()
        current_char_count = 0

        for idx, result in enumerate(search_results, start=1):
            if result.chunk_id in seen_chunks:
                continue

            # Format citation header for LLM grounding
            canon_str = f" | ID: {result.canonical_id}" if result.canonical_id else ""
            header = (
                f"[Source {idx}: Document: '{result.document_name}'{canon_str} | "
                f"Version: {result.version} | Section: {result.section_context} | "
                f"Page: {result.page_number} | Chunk: {result.chunk_id}]"
            )

            block = f"{header}\n{result.content.strip()}"
            block_chars = len(block) + 2  # Including separator newlines

            # Check character and token budgets
            if current_char_count + block_chars > self.max_characters:
                logger.info(
                    "Context budget reached (%d chars). Omitting remaining %d chunks.",
                    current_char_count,
                    len(search_results) - len(seen_chunks),
                )
                if not context_blocks:
                    # Include at least the top-1 result truncated to fit within budget
                    available_len = max(50, self.max_characters - len(header) - 10)
                    truncated_content = result.content.strip()[:available_len] + "..."
                    block = f"{header}\n{truncated_content}"
                    context_blocks.append(block)
                    seen_chunks.add(result.chunk_id)
                    citations.append(
                        Citation(
                            chunk_id=result.chunk_id,
                            document_id=result.document_id,
                            document_name=result.document_name,
                            canonical_id=result.canonical_id,
                            version=result.version,
                            section_context=result.section_context,
                            page_number=result.page_number,
                            text_excerpt=truncated_content[: self.excerpt_length],
                        )
                    )
                break

            context_blocks.append(block)
            current_char_count += block_chars
            seen_chunks.add(result.chunk_id)

            # Build Citation model
            clean_content = result.content.strip().replace("\n", " ")
            excerpt = (
                clean_content[: self.excerpt_length] + "..."
                if len(clean_content) > self.excerpt_length
                else clean_content
            )

            citation = Citation(
                chunk_id=result.chunk_id,
                document_id=result.document_id,
                document_name=result.document_name,
                canonical_id=result.canonical_id,
                version=result.version,
                section_context=result.section_context,
                page_number=result.page_number,
                text_excerpt=excerpt,
            )
            citations.append(citation)

        full_context_text = "\n\n---\n\n".join(context_blocks)
        token_estimate = _estimate_tokens(full_context_text)

        return ContextResult(
            context_text=full_context_text,
            citations=citations,
            chunk_count=len(citations),
            token_estimate=token_estimate,
            total_characters=len(full_context_text),
        )
