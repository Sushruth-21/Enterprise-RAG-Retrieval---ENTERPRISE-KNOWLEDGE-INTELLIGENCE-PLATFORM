import logging
import statistics
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pymupdf as fitz

from .base import BaseParser
from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement

logger = logging.getLogger("document_intelligence.parsers.pdf")


class PDFParser(BaseParser):
    """
    High-accuracy PDF parser combining PyMuPDF layout analysis and Docling integration.
    Extracts titles, headings, and tables preserving strict page numbers and grid structure.
    """

    supported_extensions: Set[str] = {"pdf"}
    supported_mime_types: Set[str] = {"application/pdf"}

    def __init__(self, preferred_engine: str = "pymupdf"):
        """
        :param preferred_engine: 'pymupdf' or 'docling'.
               Defaults to fast native PyMuPDF layout analysis and table extraction.
               Pass 'docling' to activate the IBM Docling transformer pipeline.
        """
        self.preferred_engine = preferred_engine.lower()

    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        engine = kwargs.get("engine", self.preferred_engine)

        if engine == "docling":
            try:
                import docling
                return self._parse_with_docling(file_path, **kwargs)
            except (ImportError, Exception) as e:
                logger.warning(f"Docling engine failed ({e}); falling back to PyMuPDF.")

        return self._parse_with_pymupdf(file_path, **kwargs)

    # =========================================================================
    # PyMuPDF Engine (Fast, Robust, Native Grid Table & Layout Extraction)
    # =========================================================================
    def _parse_with_pymupdf(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        doc = fitz.open(str(file_path))

        if doc.is_encrypted:
            # Try empty password
            if not doc.authenticate(""):
                raise ValueError(f"PDF document is encrypted/password-protected: {file_path.name}")

        total_pages = len(doc)
        if total_pages == 0:
            return ParsedDocument(
                file_path=str(file_path),
                file_type="pdf",
                total_pages=0,
                success=True,
                raw_text="",
            )

        # 1. First pass: Compute font size distribution across document to detect base body size
        body_font_size = self._estimate_body_font_size(doc)

        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        raw_text_parts: List[str] = []
        hierarchy_stack: List[Tuple[int, str]] = []
        doc_title: Optional[str] = None

        # 2. Second pass: Extract page-by-page tables and structural blocks
        for page_idx in range(total_pages):
            page = doc[page_idx]
            page_num = page_idx + 1

            # A. Extract tables on this page using PyMuPDF table finder
            page_tables, table_bboxes = self._extract_pymupdf_tables(page, page_num)
            for pt in page_tables:
                tables.append(pt)
                raw_text_parts.append(pt.markdown)

            # B. Extract text blocks and spans (excluding regions covered by tables)
            text_page = page.get_text("dict")
            blocks = text_page.get("blocks", [])

            # Sort blocks in reading order (top to bottom, left to right)
            blocks = sorted(blocks, key=lambda b: (b.get("bbox", [0, 0, 0, 0])[1], b.get("bbox", [0, 0, 0, 0])[0]))

            for block in blocks:
                # Skip image blocks
                if block.get("type") != 0:
                    continue

                bbox = fitz.Rect(block.get("bbox"))

                # If this block overlaps with an extracted table, skip it to prevent duplicating table text
                if any(bbox.intersects(tb_rect) for tb_rect in table_bboxes):
                    continue

                # Process text lines and spans within the block
                block_text, max_font_size, is_bold = self._analyze_block_spans(block)
                clean_text = block_text.strip()
                if not clean_text:
                    continue

                raw_text_parts.append(clean_text)

                # Classify element hierarchy based on font metrics
                elem_type, level = self._classify_text_element(
                    clean_text, max_font_size, is_bold, body_font_size
                )

                if elem_type in (ElementType.TITLE, ElementType.HEADING_1, ElementType.HEADING_2, ElementType.HEADING_3):
                    if doc_title is None and elem_type in (ElementType.TITLE, ElementType.HEADING_1):
                        doc_title = clean_text
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level or 1, clean_text)
                else:
                    active_hierarchy = [item[1] for item in hierarchy_stack]

                elements.append(
                    StructuralElement(
                        element_type=elem_type,
                        content=clean_text,
                        page_number=page_num,
                        heading_hierarchy=list(active_hierarchy),
                        heading_level=level,
                        metadata={
                            "font_size": round(max_font_size, 2),
                            "is_bold": is_bold,
                            "bbox": [round(c, 2) for c in block.get("bbox", [])],
                        },
                    )
                )

            # Also interleave the extracted tables as structural elements in page stream
            for pt in page_tables:
                current_hierarchy = [item[1] for item in hierarchy_stack]
                elements.append(
                    StructuralElement(
                        element_type=ElementType.TABLE,
                        content=pt.markdown,
                        page_number=page_num,
                        heading_hierarchy=list(current_hierarchy),
                        metadata={"columns": len(pt.headers), "rows": len(pt.rows)},
                    )
                )

        # Fallback title if none was classified
        if not doc_title and doc.metadata.get("title"):
            doc_title = doc.metadata.get("title")
        if not doc_title:
            doc_title = file_path.stem.replace("_", " ").title()

        return ParsedDocument(
            file_path=str(file_path),
            file_type="pdf",
            title=doc_title,
            raw_text="\n\n".join(raw_text_parts),
            elements=elements,
            tables=tables,
            total_pages=total_pages,
            success=True,
            metadata={
                "engine": "pymupdf",
                "estimated_body_font_size": body_font_size,
                "pdf_metadata": doc.metadata,
                "table_count": len(tables),
                "element_count": len(elements),
            },
        )

    def _extract_pymupdf_tables(self, page: fitz.Page, page_num: int) -> Tuple[List[ParsedTable], List[fitz.Rect]]:
        """Finds tables on page using PyMuPDF's table extraction engine and converts to Markdown."""
        extracted_tables: List[ParsedTable] = []
        table_bboxes: List[fitz.Rect] = []

        try:
            tabs = page.find_tables()
            for tab in tabs:
                raw_matrix = tab.extract()
                if not raw_matrix or len(raw_matrix) == 0:
                    continue

                # Strip empty rows and cells
                cleaned_matrix = []
                for row in raw_matrix:
                    cleaned_row = [str(c).strip() if c is not None else "" for c in row]
                    if any(c for c in cleaned_row):
                        cleaned_matrix.append(cleaned_row)

                if not cleaned_matrix:
                    continue

                headers = cleaned_matrix[0]
                data_rows = cleaned_matrix[1:] if len(cleaned_matrix) > 1 else []

                md_table = self.format_markdown_table(headers, data_rows)
                extracted_tables.append(
                    ParsedTable(
                        markdown=md_table,
                        headers=headers,
                        rows=data_rows,
                        page_number=page_num,
                    )
                )
                table_bboxes.append(fitz.Rect(tab.bbox))
        except Exception as e:
            logger.warning(f"PyMuPDF table extraction warning on page {page_num}: {e}")

        return extracted_tables, table_bboxes

    def _estimate_body_font_size(self, doc: fitz.Document) -> float:
        """Sample text spans to determine median body font size."""
        font_sizes: List[float] = []
        # Sample first 5 pages or all
        pages_to_sample = min(5, len(doc))
        for i in range(pages_to_sample):
            text_dict = doc[i].get_text("dict")
            for block in text_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            text = span.get("text", "").strip()
                            if len(text) > 2:
                                font_sizes.append(round(span.get("size", 10.0), 1))

        if not font_sizes:
            return 10.0

        # Most common font size is almost always body text
        counter = Counter(font_sizes)
        most_common = counter.most_common(1)
        return most_common[0][0] if most_common else statistics.median(font_sizes)

    def _analyze_block_spans(self, block: Dict[str, Any]) -> Tuple[str, float, bool]:
        """Aggregate text, maximum font size, and bold flags across spans in a block."""
        lines_text = []
        max_size = 0.0
        is_bold = False

        for line in block.get("lines", []):
            line_parts = []
            for span in line.get("spans", []):
                t = span.get("text", "")
                size = span.get("size", 0.0)
                flags = span.get("flags", 0)  # bit 4 (value 16) or bit 1 is bold
                if size > max_size:
                    max_size = size
                if flags & 2 or flags & 16 or "bold" in span.get("font", "").lower():
                    is_bold = True
                line_parts.append(t)
            lines_text.append("".join(line_parts))

        return " ".join(lines_text), max_size, is_bold

    def _classify_text_element(
        self, text: str, font_size: float, is_bold: bool, body_font_size: float
    ) -> Tuple[ElementType, Optional[int]]:
        """Classifies text block into Title, Heading 1/2/3, or Paragraph based on font metrics."""
        ratio = font_size / body_font_size if body_font_size > 0 else 1.0

        # Title: Very large or prominent header
        if ratio >= 1.6 or (ratio >= 1.4 and is_bold and len(text) < 100):
            return ElementType.TITLE, 1

        # Heading 1: Noticeably larger and bold, or all caps
        if ratio >= 1.35 or (ratio >= 1.25 and is_bold):
            return ElementType.HEADING_1, 1

        # Heading 2: Moderately larger or bold with short text
        if ratio >= 1.15 and is_bold and len(text) < 140:
            return ElementType.HEADING_2, 2

        # Heading 3 / Subheading: Bold at body size with short header-like phrasing
        if is_bold and ratio >= 1.05 and len(text.split()) <= 10 and not text.endswith("."):
            return ElementType.HEADING_3, 3

        return ElementType.PARAGRAPH, None

    # =========================================================================
    # Docling Engine (Deep Document Layout & Table Transformer)
    # =========================================================================
    def _parse_with_docling(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        """Parses document using IBM Docling DocumentConverter."""
        from docling.document_converter import DocumentConverter

        converter = DocumentConverter()
        conv_result = converter.convert(str(file_path))
        docling_doc = conv_result.document

        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        hierarchy_stack: List[Tuple[int, str]] = []
        raw_text_parts: List[str] = []
        doc_title: Optional[str] = getattr(docling_doc, "name", None)

        total_pages = 1

        # Docling provides structured iterate_items
        for item, level in docling_doc.iterate_items():
            page_num = 1
            if hasattr(item, "prov") and item.prov:
                page_num = item.prov[0].page_no
                if page_num > total_pages:
                    total_pages = page_num

            # Check if item is a Table
            if hasattr(item, "export_to_markdown") and hasattr(item, "data"):
                md_table = item.export_to_markdown()
                raw_text_parts.append(md_table)

                headers = []
                data_rows = []
                if hasattr(item.data, "table_cells"):
                    # Extract rows from grid
                    grid = getattr(item.data, "grid", [])
                    if grid:
                        headers = [str(c.text) for c in grid[0]]
                        data_rows = [[str(c.text) for c in row] for row in grid[1:]]

                parsed_table = ParsedTable(
                    markdown=md_table,
                    headers=headers,
                    rows=data_rows,
                    page_number=page_num,
                )
                tables.append(parsed_table)

                current_hierarchy = [h[1] for h in hierarchy_stack]
                elements.append(
                    StructuralElement(
                        element_type=ElementType.TABLE,
                        content=md_table,
                        page_number=page_num,
                        heading_hierarchy=list(current_hierarchy),
                    )
                )
            else:
                # Text item (heading or paragraph)
                label = getattr(item, "label", "text").lower()
                text = getattr(item, "text", "").strip()
                if not text:
                    continue

                raw_text_parts.append(text)

                if "title" in label:
                    if not doc_title:
                        doc_title = text
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, 1, text)
                    elem_type = ElementType.TITLE
                    h_level = 1
                elif "section_header" in label or "heading" in label:
                    h_level = min(max(level, 1), 3)
                    elem_type = (
                        ElementType.HEADING_1
                        if h_level == 1
                        else (ElementType.HEADING_2 if h_level == 2 else ElementType.HEADING_3)
                    )
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, h_level, text)
                else:
                    elem_type = ElementType.PARAGRAPH
                    h_level = None
                    active_hierarchy = [h[1] for h in hierarchy_stack]

                elements.append(
                    StructuralElement(
                        element_type=elem_type,
                        content=text,
                        page_number=page_num,
                        heading_hierarchy=list(active_hierarchy),
                        heading_level=h_level,
                    )
                )

        return ParsedDocument(
            file_path=str(file_path),
            file_type="pdf",
            title=doc_title or file_path.stem.replace("_", " ").title(),
            raw_text="\n\n".join(raw_text_parts),
            elements=elements,
            tables=tables,
            total_pages=total_pages,
            success=True,
            metadata={"engine": "docling", "table_count": len(tables), "element_count": len(elements)},
        )
