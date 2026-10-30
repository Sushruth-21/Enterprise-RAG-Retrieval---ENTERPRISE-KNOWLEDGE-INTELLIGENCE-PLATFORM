import re
from pathlib import Path
from typing import Any, List, Optional, Set

from .base import BaseParser
from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement


class MarkdownParser(BaseParser):
    """
    Parser for Markdown (.md) documents.
    Extracts headings, tables, and paragraphs while maintaining structural hierarchy and page markers.
    """

    supported_extensions: Set[str] = {"md", "markdown"}
    supported_mime_types: Set[str] = {"text/markdown", "text/x-markdown"}

    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()

        lines = content.splitlines()
        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        hierarchy_stack: List[tuple[int, str]] = []

        current_page = 1
        doc_title: Optional[str] = None

        i = 0
        n = len(lines)

        while i < n:
            line = lines[i]
            stripped = line.strip()

            # 1. Page break indicators
            if re.match(r"^<!--\s*Page\s*(\d+)\s*-->", stripped, re.IGNORECASE):
                match = re.match(r"^<!--\s*Page\s*(\d+)\s*-->", stripped, re.IGNORECASE)
                if match:
                    current_page = int(match.group(1))
                i += 1
                continue
            elif stripped in {"\\newpage", "\\pagebreak"} or "\f" in line:
                current_page += 1
                i += 1
                continue

            # 2. Blank lines
            if not stripped:
                i += 1
                continue

            # 3. Heading extraction (# Title/H1, ## H2, ### H3)
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if heading_match:
                level = len(heading_match.group(1))
                text = heading_match.group(2).strip()

                if level == 1:
                    elem_type = ElementType.HEADING_1
                    if doc_title is None:
                        doc_title = text
                elif level == 2:
                    elem_type = ElementType.HEADING_2
                else:
                    elem_type = ElementType.HEADING_3

                active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level, text)

                elements.append(
                    StructuralElement(
                        element_type=elem_type,
                        content=text,
                        page_number=current_page,
                        heading_hierarchy=list(active_hierarchy),
                        heading_level=level,
                    )
                )
                i += 1
                continue

            # 4. Table extraction (| Header | ... |)
            if stripped.startswith("|") and stripped.endswith("|") and i + 1 < n and ("---" in lines[i + 1]):
                table_lines = []
                while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                    table_lines.append(lines[i].strip())
                    i += 1

                parsed_table = self._parse_markdown_table_block(table_lines, current_page)
                if parsed_table:
                    tables.append(parsed_table)
                    current_hierarchy = [item[1] for item in hierarchy_stack]
                    elements.append(
                        StructuralElement(
                            element_type=ElementType.TABLE,
                            content=parsed_table.markdown,
                            page_number=current_page,
                            heading_hierarchy=list(current_hierarchy),
                            metadata={"columns": len(parsed_table.headers), "rows": len(parsed_table.rows)},
                        )
                    )
                continue

            # 5. Regular text / paragraph accumulator
            para_lines = [line]
            i += 1
            while i < n:
                next_line = lines[i]
                next_stripped = next_line.strip()
                if (
                    not next_stripped
                    or re.match(r"^#{1,6}\s+", next_stripped)
                    or (next_stripped.startswith("|") and "---" in (lines[i + 1] if i + 1 < n else ""))
                    or re.match(r"^<!--\s*Page", next_stripped, re.IGNORECASE)
                ):
                    break
                para_lines.append(next_line)
                i += 1

            paragraph_text = "\n".join(para_lines).strip()
            if paragraph_text:
                current_hierarchy = [item[1] for item in hierarchy_stack]
                elements.append(
                    StructuralElement(
                        element_type=ElementType.PARAGRAPH,
                        content=paragraph_text,
                        page_number=current_page,
                        heading_hierarchy=list(current_hierarchy),
                    )
                )

        return ParsedDocument(
            file_path=str(file_path),
            file_type="md",
            title=doc_title or file_path.stem.replace("_", " ").title(),
            raw_text=content,
            elements=elements,
            tables=tables,
            total_pages=max(current_page, 1),
            success=True,
            metadata={"total_elements": len(elements), "table_count": len(tables)},
        )

    def _parse_markdown_table_block(self, lines: List[str], page_number: int) -> Optional[ParsedTable]:
        """Parses a block of markdown table lines into headers, rows, and clean grid markdown."""
        if len(lines) < 2:
            return None

        def split_row(line_str: str) -> List[str]:
            raw_cells = line_str.strip().strip("|").split("|")
            return [c.strip() for c in raw_cells]

        headers = split_row(lines[0])
        # Line 1 is the delimiter line (e.g. |---|---|)
        data_rows = [split_row(l) for l in lines[2:]]

        clean_md = self.format_markdown_table(headers, data_rows)
        return ParsedTable(
            markdown=clean_md,
            headers=headers,
            rows=data_rows,
            page_number=page_number,
        )
