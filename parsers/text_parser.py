import re
from pathlib import Path
from typing import Any, List, Optional, Set

from .base import BaseParser
from .models import ElementType, ParsedDocument, ParsedTable, StructuralElement


class TextParser(BaseParser):
    """
    Parser for plain text (.txt) files.
    Applies heuristic structural analysis to identify headings, sections, and ASCII tables.
    """

    supported_extensions: Set[str] = {"txt", "text", "log"}
    supported_mime_types: Set[str] = {"text/plain"}

    def _parse_document(self, file_path: Path, **kwargs: Any) -> ParsedDocument:
        # Try UTF-8 first, fallback to latin-1
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="latin-1") as f:
                content = f.read()

        page_chunks = content.split("\f")
        elements: List[StructuralElement] = []
        tables: List[ParsedTable] = []
        hierarchy_stack: List[tuple[int, str]] = []
        doc_title: Optional[str] = None

        for page_idx, page_text in enumerate(page_chunks):
            current_page = page_idx + 1
            lines = page_text.splitlines()
            i = 0
            n = len(lines)

            while i < n:
                line = lines[i]
                stripped = line.strip()

                if not stripped:
                    i += 1
                    continue

                # Underlined headings (e.g., Line followed by "====" or "----")
                if i + 1 < n and (
                    (set(lines[i + 1].strip()) == {"="} and len(lines[i + 1].strip()) >= 3)
                    or (set(lines[i + 1].strip()) == {"-"} and len(lines[i + 1].strip()) >= 3)
                ):
                    level = 1 if set(lines[i + 1].strip()) == {"="} else 2
                    elem_type = ElementType.HEADING_1 if level == 1 else ElementType.HEADING_2
                    heading_text = stripped

                    if doc_title is None and level == 1:
                        doc_title = heading_text

                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level, heading_text)
                    elements.append(
                        StructuralElement(
                            element_type=elem_type,
                            content=heading_text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=level,
                        )
                    )
                    i += 2  # skip the underline
                    continue

                # Numbered headings (e.g. "1. Overview", "2.1 Scope", "SECTION 1:")
                numbered_match = re.match(r"^(\d+(\.\d+)*|[A-Z]\.)\s+([A-Z0-9].*)$", stripped)
                all_caps_match = stripped.isupper() and len(stripped.split()) <= 8 and len(stripped) >= 3

                if numbered_match or all_caps_match:
                    if numbered_match:
                        prefix = numbered_match.group(1)
                        depth = prefix.count(".") + 1
                        heading_text = stripped
                    else:
                        depth = 1
                        heading_text = stripped

                    level = min(depth, 3)
                    elem_type = (
                        ElementType.HEADING_1
                        if level == 1
                        else (ElementType.HEADING_2 if level == 2 else ElementType.HEADING_3)
                    )

                    if doc_title is None and level == 1:
                        doc_title = heading_text

                    active_hierarchy = self.update_heading_hierarchy(hierarchy_stack, level, heading_text)
                    elements.append(
                        StructuralElement(
                            element_type=elem_type,
                            content=heading_text,
                            page_number=current_page,
                            heading_hierarchy=list(active_hierarchy),
                            heading_level=level,
                        )
                    )
                    i += 1
                    continue

                # Markdown/ASCII-style table check in text files
                if stripped.startswith("|") and stripped.endswith("|") and i + 1 < n and ("---" in lines[i + 1]):
                    table_lines = []
                    while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                        table_lines.append(lines[i].strip())
                        i += 1

                    parsed_table = self._parse_text_table_block(table_lines, current_page)
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

                # Standard paragraph
                para_lines = [line]
                i += 1
                while i < n:
                    next_line = lines[i]
                    next_stripped = next_line.strip()
                    if (
                        not next_stripped
                        or (next_stripped.isupper() and len(next_stripped.split()) <= 8)
                        or re.match(r"^(\d+(\.\d+)*|[A-Z]\.)\s+", next_stripped)
                        or (next_stripped.startswith("|") and "---" in (lines[i + 1] if i + 1 < n else ""))
                    ):
                        break
                    para_lines.append(next_line)
                    i += 1

                paragraph_text = " ".join(l.strip() for l in para_lines).strip()
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
            file_type="txt",
            title=doc_title or file_path.stem.replace("_", " ").title(),
            raw_text=content,
            elements=elements,
            tables=tables,
            total_pages=max(len(page_chunks), 1),
            success=True,
            metadata={"total_elements": len(elements), "table_count": len(tables)},
        )

    def _parse_text_table_block(self, lines: List[str], page_number: int) -> Optional[ParsedTable]:
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
