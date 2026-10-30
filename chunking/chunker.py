import hashlib
import logging
import uuid
from typing import List, Optional
from uuid import UUID

from models.enums import DocumentStatus, ProcessingStatus
from models.schemas import ChunkModel
from parsers.models import ElementType, ParsedDocument, StructuralElement
from .tokenizer import count_tokens

logger = logging.getLogger("document_intelligence.chunking")


class StructureAwareChunker:
    """
    Intelligent structure-aware chunker for ParsedDocument intermediate representations.
    
    Key Features:
    - Preserves paragraph and table integrity (never cuts tables arbitrarily).
    - Groups tables with their preceding introductory text.
    - Prepends hierarchical section breadcrumbs to each chunk.
    - Computes SHA-256 hashes of chunk content for incremental embedding.
    - Emits sequentially ordered ChunkModel instances adhering to the pgvector integration contract.
    """

    def __init__(
        self,
        min_tokens: int = 500,
        max_tokens: int = 800,
        default_embedding_model: str = "BAAI/bge-small-en-v1.5",
    ):
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.default_embedding_model = default_embedding_model

    def chunk_document(
        self,
        parsed_doc: ParsedDocument,
        document_id: UUID,
        organization_id: UUID,
        document_name: Optional[str] = None,
        version: str = "1.0",
        document_status: DocumentStatus = DocumentStatus.CURRENT,
        embedding_model: Optional[str] = None,
    ) -> List[ChunkModel]:
        """
        Main entrypoint: Transforms a ParsedDocument into an ordered sequence of ChunkModel instances.
        """
        doc_name = document_name or parsed_doc.title or "Untitled Document"
        emb_model = embedding_model or self.default_embedding_model

        if not parsed_doc.elements:
            return []

        chunks: List[ChunkModel] = []
        current_elements: List[StructuralElement] = []
        current_section_context = self._resolve_section_context(parsed_doc.elements[0], parsed_doc.title)

        for element in parsed_doc.elements:
            element_section = self._resolve_section_context(element, parsed_doc.title)

            # If element is a table, apply table-grouping logic
            if element.element_type == ElementType.TABLE:
                chunks.extend(
                    self._handle_table_element(
                        element=element,
                        current_elements=current_elements,
                        current_section=current_section_context,
                        chunks=chunks,
                        doc_id=document_id,
                        org_id=organization_id,
                        doc_name=doc_name,
                        version=version,
                        doc_status=document_status,
                        emb_model=emb_model,
                    )
                )
                current_elements.clear()
                current_section_context = element_section
                continue

            # Check if adding this element exceeds max_tokens or crosses a major section boundary
            combined_elements = current_elements + [element]
            combined_tokens = self._calculate_chunk_tokens(current_section_context, combined_elements)

            if combined_tokens > self.max_tokens and current_elements:
                # Flush current buffer as a completed chunk
                chunk = self._build_chunk(
                    elements=current_elements,
                    section_context=current_section_context,
                    chunk_index=len(chunks),
                    doc_id=document_id,
                    org_id=organization_id,
                    doc_name=doc_name,
                    version=version,
                    doc_status=document_status,
                    emb_model=emb_model,
                )
                chunks.append(chunk)
                current_elements = [element]
                current_section_context = element_section
            else:
                current_elements.append(element)
                # Keep active section context updated
                if element.heading_hierarchy:
                    current_section_context = element_section

        # Flush any remaining elements in buffer
        if current_elements:
            chunk = self._build_chunk(
                elements=current_elements,
                section_context=current_section_context,
                chunk_index=len(chunks),
                doc_id=document_id,
                org_id=organization_id,
                doc_name=doc_name,
                version=version,
                doc_status=document_status,
                emb_model=emb_model,
            )
            chunks.append(chunk)

        logger.info(
            f"Chunked document '{doc_name}' ({parsed_doc.total_pages} pages) into {len(chunks)} chunks."
        )
        return chunks

    def _handle_table_element(
        self,
        element: StructuralElement,
        current_elements: List[StructuralElement],
        current_section: str,
        chunks: List[ChunkModel],
        doc_id: UUID,
        org_id: UUID,
        doc_name: str,
        version: str,
        doc_status: DocumentStatus,
        emb_model: str,
    ) -> List[ChunkModel]:
        """
        Groups table with preceding explanatory/introductory paragraph if present,
        or handles splitting oversized tables row-by-row preserving headers.
        """
        table_chunks: List[ChunkModel] = []
        table_text = element.content

        # Identify if the last element in current_elements is introductory text for the table
        explanatory_element: Optional[StructuralElement] = None
        prior_elements: List[StructuralElement] = []

        if current_elements:
            last_elem = current_elements[-1]
            if last_elem.element_type == ElementType.PARAGRAPH and (
                last_elem.content.strip().endswith(":")
                or any(keyword in last_elem.content.lower() for keyword in ["table", "below", "following", "schedule", "matrix"])
                or len(last_elem.content.split()) <= 40
            ):
                explanatory_element = last_elem
                prior_elements = current_elements[:-1]
            else:
                prior_elements = current_elements

        # Flush prior elements that won't fit with the table
        if prior_elements:
            chunk = self._build_chunk(
                elements=prior_elements,
                section_context=current_section,
                chunk_index=len(chunks) + len(table_chunks),
                doc_id=doc_id,
                org_id=org_id,
                doc_name=doc_name,
                version=version,
                doc_status=doc_status,
                emb_model=emb_model,
            )
            table_chunks.append(chunk)

        # Elements to bundle with the table
        table_bundle = [explanatory_element, element] if explanatory_element else [element]
        bundle_tokens = self._calculate_chunk_tokens(current_section, table_bundle)

        if bundle_tokens <= self.max_tokens:
            # Table fits cleanly inside max_tokens with explanatory text
            chunk = self._build_chunk(
                elements=table_bundle,
                section_context=current_section,
                chunk_index=len(chunks) + len(table_chunks),
                doc_id=doc_id,
                org_id=org_id,
                doc_name=doc_name,
                version=version,
                doc_status=doc_status,
                emb_model=emb_model,
            )
            table_chunks.append(chunk)
        else:
            # Table is oversized (> max_tokens): split row-by-row with header replication
            sub_tables = self._split_large_table(table_text, self.max_tokens - 100)
            for idx, sub_tbl_text in enumerate(sub_tables):
                sub_element = StructuralElement(
                    element_type=ElementType.TABLE,
                    content=sub_tbl_text,
                    page_number=element.page_number,
                    heading_hierarchy=element.heading_hierarchy,
                    metadata={"sub_table_index": idx},
                )
                sub_bundle = [explanatory_element, sub_element] if (idx == 0 and explanatory_element) else [sub_element]
                chunk = self._build_chunk(
                    elements=sub_bundle,
                    section_context=current_section,
                    chunk_index=len(chunks) + len(table_chunks),
                    doc_id=doc_id,
                    org_id=org_id,
                    doc_name=doc_name,
                    version=version,
                    doc_status=doc_status,
                    emb_model=emb_model,
                )
                table_chunks.append(chunk)

        return table_chunks

    def _split_large_table(self, markdown_table: str, target_tokens: int) -> List[str]:
        """
        Splits a markdown table by rows while repeating the header row on every slice.
        """
        lines = markdown_table.strip().splitlines()
        if len(lines) <= 3:
            return [markdown_table]

        header_lines = lines[:2]  # Header text + delimiter line
        data_rows = lines[2:]

        slices: List[str] = []
        current_rows: List[str] = []

        for row in data_rows:
            candidate = "\n".join(header_lines + current_rows + [row])
            if count_tokens(candidate) > target_tokens and current_rows:
                slices.append("\n".join(header_lines + current_rows))
                current_rows = [row]
            else:
                current_rows.append(row)

        if current_rows:
            slices.append("\n".join(header_lines + current_rows))

        return slices or [markdown_table]

    def _build_chunk(
        self,
        elements: List[StructuralElement],
        section_context: str,
        chunk_index: int,
        doc_id: UUID,
        org_id: UUID,
        doc_name: str,
        version: str,
        doc_status: DocumentStatus,
        emb_model: str,
    ) -> ChunkModel:
        """Constructs a fully populated ChunkModel with context header and SHA-256 hash."""
        page_numbers = [el.page_number for el in elements if el.page_number is not None]
        primary_page = page_numbers[0] if page_numbers else 1

        # Format chunk content with prepended hierarchical context
        body_text = "\n\n".join(el.content.strip() for el in elements if el.content.strip())
        formatted_content = f"[{section_context}]\n\n{body_text}"

        chunk_hash = hashlib.sha256(formatted_content.encode("utf-8")).hexdigest()

        return ChunkModel(
            chunk_id=uuid.uuid4(),
            organization_id=org_id,
            document_id=doc_id,
            document_name=doc_name,
            version=version,
            chunk_index=chunk_index,
            section_context=section_context,
            page_number=primary_page,
            content=formatted_content,
            chunk_hash=chunk_hash,
            embedding_model=emb_model,
            processing_status=ProcessingStatus.PENDING,
            document_status=doc_status,
        )

    def _resolve_section_context(self, element: StructuralElement, fallback_title: Optional[str]) -> str:
        """Formats the hierarchical section breadcrumbs."""
        if element.heading_hierarchy:
            return " > ".join(element.heading_hierarchy)
        return fallback_title or "General Overview"

    def _calculate_chunk_tokens(self, section_context: str, elements: List[StructuralElement]) -> int:
        """Computes total tokens for section header plus all body elements."""
        body = "\n\n".join(el.content.strip() for el in elements)
        full_text = f"[{section_context}]\n\n{body}"
        return count_tokens(full_text)


def split_document_into_chunks(
    parsed_doc: ParsedDocument,
    document_id: UUID,
    organization_id: UUID,
    document_name: Optional[str] = None,
    version: str = "1.0",
    document_status: DocumentStatus = DocumentStatus.CURRENT,
    embedding_model: str = "BAAI/bge-small-en-v1.5",
    min_tokens: int = 500,
    max_tokens: int = 800,
) -> List[ChunkModel]:
    """
    Convenience function to chunk a ParsedDocument with default settings.
    """
    chunker = StructureAwareChunker(
        min_tokens=min_tokens,
        max_tokens=max_tokens,
        default_embedding_model=embedding_model,
    )
    return chunker.chunk_document(
        parsed_doc=parsed_doc,
        document_id=document_id,
        organization_id=organization_id,
        document_name=document_name,
        version=version,
        document_status=document_status,
        embedding_model=embedding_model,
    )
