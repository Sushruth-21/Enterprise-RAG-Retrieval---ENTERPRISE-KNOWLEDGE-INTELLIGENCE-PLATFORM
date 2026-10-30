from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ElementType(str, Enum):
    """Types of structural document elements identified during parsing."""
    TITLE = "title"
    HEADING_1 = "heading_1"
    HEADING_2 = "heading_2"
    HEADING_3 = "heading_3"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    LIST_ITEM = "list_item"
    CODE = "code"


class StructuralElement(BaseModel):
    """
    An extracted discrete structural element from the document,
    maintaining page awareness and hierarchical heading lineage.
    """
    model_config = ConfigDict(from_attributes=True)

    element_type: ElementType = Field(
        ...,
        description="Categorical type of the extracted element",
    )
    content: str = Field(
        ...,
        min_length=1,
        description="Extracted text or formatted markdown table content",
    )
    page_number: int = Field(
        ...,
        ge=1,
        description="1-indexed physical page number where element was located",
    )
    heading_hierarchy: List[str] = Field(
        default_factory=list,
        description="Breadcrumbs of active ancestor headings (e.g. ['1. Policies', '1.2 Travel'])",
    )
    heading_level: Optional[int] = Field(
        default=None,
        description="Heading depth (1 for H1, 2 for H2, 3 for H3, etc.), or None for body text",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata (font size, bounding box coordinates, column counts, etc.)",
    )


class ParsedTable(BaseModel):
    """
    Structured extraction of a table, preserving grid semantics and markdown representation.
    """
    model_config = ConfigDict(from_attributes=True)

    markdown: str = Field(
        ...,
        description="Clean, valid GitHub-flavored Markdown table representation with grid dividers",
    )
    headers: List[str] = Field(
        default_factory=list,
        description="List of column headers extracted from the table's first row",
    )
    rows: List[List[str]] = Field(
        default_factory=list,
        description="2D matrix of cell values across rows and columns",
    )
    page_number: int = Field(
        ...,
        ge=1,
        description="1-indexed page number containing the table",
    )
    caption: Optional[str] = Field(
        default=None,
        description="Table caption or preceding identifying title if detected",
    )


class ParsedDocument(BaseModel):
    """
    Intermediate representation of a parsed document before chunking.
    Contains raw text mapped to structural elements, page numbers, and tables.
    """
    model_config = ConfigDict(from_attributes=True)

    file_path: str = Field(..., description="Source path or URI of the parsed document")
    file_type: str = Field(..., description="Extension or detected MIME type (e.g., 'pdf', 'docx')")
    title: Optional[str] = Field(default=None, description="Primary document title if discovered")
    raw_text: str = Field(default="", description="Complete reconstructed text of the document")
    elements: List[StructuralElement] = Field(
        default_factory=list,
        description="Chronological sequence of extracted structural elements",
    )
    tables: List[ParsedTable] = Field(
        default_factory=list,
        description="List of all extracted tables in the document",
    )
    total_pages: int = Field(
        default=1,
        ge=0,
        description="Total page count of the document",
    )
    success: bool = Field(
        default=True,
        description="Flag indicating whether parsing completed without critical unrecoverable errors",
    )
    error_message: Optional[str] = Field(
        default=None,
        description="Error description if document parsing encountered failure or degradation",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parser engine metadata (e.g., engine name, extraction duration, author)",
    )

    def get_headings(self) -> List[StructuralElement]:
        """Return all elements that are titles or headings."""
        heading_types = {
            ElementType.TITLE,
            ElementType.HEADING_1,
            ElementType.HEADING_2,
            ElementType.HEADING_3,
        }
        return [el for el in self.elements if el.element_type in heading_types]

    def get_elements_by_page(self, page_number: int) -> List[StructuralElement]:
        """Filter extracted elements for a specific 1-indexed page."""
        return [el for el in self.elements if el.page_number == page_number]

    def get_full_markdown(self) -> str:
        """Render the complete document as structured Markdown."""
        chunks = []
        current_page = None
        for el in self.elements:
            if el.page_number != current_page:
                current_page = el.page_number
                chunks.append(f"\n<!-- Page {current_page} -->\n")
            if el.element_type == ElementType.TITLE:
                chunks.append(f"# {el.content}\n")
            elif el.element_type == ElementType.HEADING_1:
                chunks.append(f"# {el.content}\n")
            elif el.element_type == ElementType.HEADING_2:
                chunks.append(f"## {el.content}\n")
            elif el.element_type == ElementType.HEADING_3:
                chunks.append(f"### {el.content}\n")
            elif el.element_type == ElementType.TABLE:
                chunks.append(f"\n{el.content}\n")
            else:
                chunks.append(f"{el.content}\n")
        return "\n".join(chunks).strip()
