import logging
import re
from pathlib import Path
from typing import Any, List, Optional, Set

from ocr import HybridOCREngine, OCRResult
from .base import BaseParser
from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement

logger = logging.getLogger("document_intelligence.parsers.image")


class ImageParser(BaseParser):
    """
    Parser for standalone image documents (PNG, JPEG, TIFF, WEBP, BMP).
    Utilizes HybridOCREngine (fast offline RapidOCR with online Gemini 2.0 Flash fail-safe).
    """

    supported_extensions: Set[str] = {"png", "jpg", "jpeg", "tiff", "tif", "webp", "bmp"}
    supported_mime_types: Set[str] = {
        "image/png",
        "image/jpeg",
        "image/tiff",
        "image/webp",
        "image/bmp",
    }

    def __init__(self, ocr_mode: str = "auto", confidence_threshold: float = 0.65):
        self.ocr_engine = HybridOCREngine(mode=ocr_mode, confidence_threshold=confidence_threshold)

    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        logger.info(f"Parsing image document: {file_path.name}")
        ocr_result: OCRResult = self.ocr_engine.extract_text(file_path)

        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        hierarchy_stack: List[tuple[int, str]] = []
        doc_title: Optional[str] = None

        lines = ocr_result.text.splitlines()
        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            # Heading checks: Markdown style (# Title) or ALL CAPS short lines
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            all_caps_header = stripped.isupper() and len(stripped.split()) <= 8 and len(stripped) >= 3

            if heading_match or all_caps_header:
                if heading_match:
                    level = len(heading_match.group(1))
                    text = heading_match.group(2).strip()
                else:
                    level = 1
                    text = stripped

                level = min(level, 3)
                elem_type = (
                    ElementType.HEADING_1
                    if level == 1
                    else (ElementType.HEADING_2 if level == 2 else ElementType.HEADING_3)
                )

                if doc_title is None and level == 1:
                    doc_title = text

                active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level, text)
                elements.append(
                    StructuralElement(
                        element_type=elem_type,
                        content=text,
                        page_number=1,
                        heading_hierarchy=list(active_hierarchy),
                        heading_level=level,
                        metadata={"ocr_engine": ocr_result.engine_used, "confidence": ocr_result.confidence},
                    )
                )
                i += 1
                continue

            # Markdown Table detection
            if stripped.startswith("|") and stripped.endswith("|") and i + 1 < n and ("---" in lines[i + 1]):
                table_lines = []
                while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                parsed_table = self._parse_image_table(table_lines, page_number=1)
                if parsed_table:
                    tables.append(parsed_table)
                    current_hierarchy = [h[1] for h in hierarchy_stack]
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.TABLE,
                            content=parsed_table.markdown,
                            page_number=1,
                            heading_hierarchy=list(current_hierarchy),
                            metadata={"columns": len(parsed_table.headers), "rows": len(parsed_table.rows)},
                        )
                    )
                continue

            # Paragraph block
            para_lines = [line]
            i += 1
            while i < n:
                next_line = lines[i]
                next_stripped = next_line.strip()
                if (
                    not next_stripped
                    or next_stripped.startswith("#")
                    or (next_stripped.isupper() and len(next_stripped.split()) <= 8)
                    or (next_stripped.startswith("|") and "---" in (lines[i + 1] if i + 1 < n else ""))
                ):
                    break
                para_lines.append(next_line)
                i += 1

            paragraph_text = " ".join(l.strip() for l in para_lines).strip()
            if paragraph_text:
                current_hierarchy = [h[1] for h in hierarchy_stack]
                elements.append(
                    StructuralElement(
                        element_type=ElementType.PARAGRAPH,
                        content=paragraph_text,
                        page_number=1,
                        heading_hierarchy=list(current_hierarchy),
                        metadata={"ocr_engine": ocr_result.engine_used},
                    )
                )

        return ParsedDocument(
            file_path=str(file_path),
            file_type=file_path.suffix.lower().lstrip("."),
            title=doc_title or file_path.stem.replace("_", " ").title(),
            raw_text=ocr_result.text,
            elements=elements,
            tables=tables,
            total_pages=1,
            success=True,
            metadata={
                "ocr_engine": ocr_result.engine_used,
                "ocr_confidence": ocr_result.confidence,
                "ocr_duration_ms": ocr_result.duration_ms,
                "fallback_triggered": ocr_result.fallback_triggered,
                "table_count": len(tables),
                "element_count": len(elements),
            },
        )

    def _parse_image_table(self, lines: List[str], page_number: int) -> Optional[ParsedTable]:
        if len(lines) < 2:
            return None
        headers = [c.strip() for c in lines[0].strip().strip("|").split("|")]
        data_rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in lines[2:]]
        clean_md = self.format_markdown_table(headers, data_rows)
        return ParsedTable(
            markdown=clean_md,
            headers=headers,
            rows=data_rows,
            page_number=page_number,
        )
