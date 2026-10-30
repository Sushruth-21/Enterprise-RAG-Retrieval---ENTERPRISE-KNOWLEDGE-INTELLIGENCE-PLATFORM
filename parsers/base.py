import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union

from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement

logger = logging.getLogger("document_intelligence.parsers")


class BaseParser(ABC):
    """
    Abstract base class for all document parsers.
    Enforces standardized error handling, table formatting, and structural element tracking.
    """

    supported_extensions: Set[str] = set()
    supported_mime_types: Set[str] = set()

    def parse(self, file_path: Union[str, Path], **kwargs: Any) -> ParsedDocument:
        """
        Public entrypoint for parsing a document.
        Wraps extraction in defensive error handling to prevent pipeline crashes.
        """
        path = Path(file_path)
        ext = path.suffix.lower().lstrip(".")

        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return ParsedDocument(
                file_path=str(path),
                file_type=ext or "unknown",
                total_pages=0,
                success=False,
                error_message=f"File not found: {file_path}",
            )

        try:
            logger.info(f"Parsing document '{path.name}' with {self.__class__.__name__}")
            parsed_doc = self._parse_document(path, **kwargs)
            return parsed_doc
        except Exception as e:
            logger.error(
                f"Failed to parse document '{path.name}' with {self.__class__.__name__}: {str(e)}",
                exc_info=True,
            )
            return ParsedDocument(
                file_path=str(path),
                file_type=ext or "unknown",
                total_pages=0,
                success=False,
                error_message=f"Extraction failure ({self.__class__.__name__}): {str(e)}",
            )

    @abstractmethod
    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        """Subclasses must implement the format-specific parsing logic."""
        raise NotImplementedError

    @staticmethod
    def format_markdown_table(headers: List[str], rows: List[List[str]]) -> str:
        """
        Formats raw headers and 2D row values into a strict, clean GitHub-Flavored Markdown table.
        Normalizes column counts, escapes pipes, and converts cell newlines to HTML breaks.
        """
        if not headers and not rows:
            return ""

        # Determine column count
        col_count = len(headers) if headers else (max(len(r) for r in rows) if rows else 0)
        if col_count == 0:
            return ""

        # Normalize headers
        clean_headers = []
        for i in range(col_count):
            h = headers[i] if i < len(headers) else f"Column {i + 1}"
            clean_headers.append(BaseParser._clean_cell_content(h))

        # Normalize rows
        clean_rows = []
        for row in rows:
            clean_row = []
            for i in range(col_count):
                val = row[i] if i < len(row) else ""
                clean_row.append(BaseParser._clean_cell_content(val))
            clean_rows.append(clean_row)

        # Build markdown lines
        lines = []
        lines.append("| " + " | ".join(clean_headers) + " |")
        lines.append("| " + " | ".join(["---"] * col_count) + " |")
        for r in clean_rows:
            lines.append("| " + " | ".join(r) + " |")

        return "\n".join(lines)

    @staticmethod
    def _clean_cell_content(cell: Any) -> str:
        """Sanitize table cell text by escaping pipes and replacing newlines."""
        if cell is None:
            return ""
        text = str(cell).strip()
        # Escape markdown pipes
        text = text.replace("|", "\\|")
        # Replace line breaks inside cells with html breaks
        text = text.replace("\r\n", "<br/>").replace("\n", "<br/>").replace("\r", "<br/>")
        return text

    @staticmethod
    def update_heading_hierarchy(
        hierarchy_stack: List[tuple[int, str]], level: int, title: str
    ) -> List[str]:
        """
        Maintains an active heading hierarchy stack based on heading depth level.
        Pop all headings of equal or deeper level, then push the new heading.
        Returns the active breadcrumb list of string titles.
        """
        while hierarchy_stack and hierarchy_stack[-1][0] >= level:
            hierarchy_stack.pop()
        hierarchy_stack.append((level, title.strip()))
        return [item[1] for item in hierarchy_stack]
