import logging
from pathlib import Path
from typing import Any, List, Optional, Set

import docx
from docx.oxml.ns import qn

from .base import BaseParser
from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement

logger = logging.getLogger("document_intelligence.parsers.docx")


class DocxParser(BaseParser):
    """
    Parser for Microsoft Word (.docx) documents.
    Extracts headings based on Word style hierarchy and paragraph semantics,
    extracts tables with full grid preservation formatted as Markdown, and tracks page breaks.
    """

    supported_extensions: Set[str] = {"docx"}
    supported_mime_types: Set[str] = {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }

    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        doc = docx.Document(str(file_path))

        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        hierarchy_stack: List[tuple[int, str]] = []

        current_page = 1
        doc_title: Optional[str] = None
        raw_text_parts: List[str] = []

        # Iterate over all block-level elements in body order (paragraphs & tables)
        for block in self._iter_block_items(doc):
            if isinstance(block, docx.text.paragraph.Paragraph):
                # Check for explicit page breaks in paragraph runs
                for run in block.runs:
                    if self._has_page_break(run):
                        current_page += 1

                text = block.text.strip()
                if not text:
                    continue

                raw_text_parts.append(text)
                style_name = (block.style.name or "").lower() if block.style else ""

                # Title detection
                if "title" in style_name:
                    if doc_title is None:
                        doc_title = text
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, 1, text)
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.TITLE,
                            content=text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=1,
                            metadata={"style": block.style.name},
                        )
                    )
                # Heading 1
                elif "heading 1" in style_name:
                    if doc_title is None:
                        doc_title = text
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, 1, text)
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.HEADING_1,
                            content=text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=1,
                            metadata={"style": block.style.name},
                        )
                    )
                # Heading 2
                elif "heading 2" in style_name:
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, 2, text)
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.HEADING_2,
                            content=text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=2,
                            metadata={"style": block.style.name},
                        )
                    )
                # Heading 3 / Subheading
                elif "heading 3" in style_name or "heading 4" in style_name or "subheading" in style_name:
                    level = 3
                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level, text)
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.HEADING_3,
                            content=text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=level,
                            metadata={"style": block.style.name},
                        )
                    )
                # Standard paragraph
                else:
                    current_hierarchy = [item[1] for item in hierarchy_stack]
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.PARAGRAPH,
                            content=text,
                            page_number=current_page,
                            heading_hierarchy=list(current_hierarchy),
                            metadata={"style": block.style.name if block.style else "Normal"},
                        )
                    )

            elif isinstance(block, docx.table.Table):
                # Table block
                headers, data_rows = self._extract_table_grid(block)
                if not headers and not data_rows:
                    continue

                md_table = self.format_markdown_table(headers, data_rows)
                raw_text_parts.append(md_table)

                parsed_table = ParsedTable(
                    markdown=md_table,
                    headers=headers,
                    rows=data_rows,
                    page_number=current_page,
                )
                tables.append(parsed_table)

                current_hierarchy = [item[1] for item in hierarchy_stack]
                elements.append(
                    StructuralElement(
                        element_type=ElementType.TABLE,
                        content=md_table,
                        page_number=current_page,
                        heading_hierarchy=list(current_hierarchy),
                        metadata={"columns": len(headers), "rows": len(data_rows)},
                    )
                )

        return ParsedDocument(
            file_path=str(file_path),
            file_type="docx",
            title=doc_title or file_path.stem.replace("_", " ").title(),
            raw_text="\n\n".join(raw_text_parts),
            elements=elements,
            tables=tables,
            total_pages=max(current_page, 1),
            success=True,
            metadata={"total_elements": len(elements), "table_count": len(tables)},
        )

    def _extract_table_grid(self, table: docx.table.Table) -> tuple[List[str], List[List[str]]]:
        """Extracts rows and cells from a python-docx Table, preserving grid cells."""
        raw_rows = []
        for row in table.rows:
            row_data = [cell.text.strip() for cell in row.cells]
            raw_rows.append(row_data)

        if not raw_rows:
            return [], []

        headers = raw_rows[0]
        data_rows = raw_rows[1:] if len(raw_rows) > 1 else []
        return headers, data_rows

    def _has_page_break(self, run: docx.text.run.Run) -> bool:
        """Inspects run XML elements for rendered or hard page breaks."""
        for child in run._r:
            if child.tag.endswith("br"):
                br_type = child.attrib.get(qn("w:type"), "")
                if br_type == "page":
                    return True
            elif child.tag.endswith("lastRenderedPageBreak"):
                return True
        return False

    @staticmethod
    def _iter_block_items(parent: docx.Document):
        """
        Yield each paragraph and table child within a Document in document order.
        """
        for child in parent.element.body:
            if child.tag.endswith("p"):
                yield docx.text.paragraph.Paragraph(child, parent)
            elif child.tag.endswith("tbl"):
                yield docx.table.Table(child, parent)
