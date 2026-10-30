# Document Intelligence Pipeline: Parsers & Schema

## Overview
This module defines the modular parsing engine, database schema, and data models for document intelligence. It supports PDF, DOCX, TXT, and Markdown extraction prior to chunking and embedding.

---

## Architecture

```
vdit/
├── models/
│   ├── __init__.py        # Package export interface
│   ├── enums.py           # DocumentStatus, ProcessingStatus
│   ├── db.py              # SQLAlchemy 2.0 schema (Document & Chunk tables)
│   └── schemas.py         # Pydantic V2 schemas for ingestion and parser validation
├── parsers/
│   ├── __init__.py        # Exports BaseParser, PDFParser, DocxParser, etc.
│   ├── models.py          # Intermediate ParsedDocument, StructuralElement, ParsedTable
│   ├── base.py            # Abstract BaseParser with defensive error handling & table formatting
│   ├── pdf_parser.py      # PyMuPDF + Docling dual-engine PDF parser
│   ├── docx_parser.py     # python-docx parser mapping style hierarchy & table grids
│   ├── markdown_parser.py # Heading & table parser with page break awareness
│   ├── text_parser.py     # Heuristic layout and section parser for plain text
│   └── factory.py         # Extension-based parser factory & parse_document helper
├── chunking/
│   ├── __init__.py        # Exports StructureAwareChunker, count_tokens
│   ├── tokenizer.py       # tiktoken token counter with heuristic fallback
│   ├── chunker.py         # Table-preserving, structure-aware chunking engine
│   └── example.py         # Runnable demonstration script
├── versioning/
│   ├── __init__.py        # Exports VersionControlManager
│   ├── exceptions.py      # DuplicateDocumentError, DocumentNotFoundError, TenantViolationError
│   └── manager.py         # Transactional lineage resolution & chunk status cascading
├── orchestrator/
│   ├── __init__.py        # Exports IngestionOrchestrator, IngestionRequest, IngestionResult
│   ├── models.py          # Ingestion contract models
│   └── pipeline.py        # End-to-end ingestion pipeline coordinator
├── scripts/
│   └── generate_mock_documents.py # Mock document generator (PDF, DOCX, TXT, MD)
├── tests/
│   ├── test_models.py     # Data model and database schema tests
│   ├── test_parsers.py    # Parser validation across PDF, DOCX, TXT, MD
│   ├── test_chunker.py    # Chunker tests for table preservation & context prepending
│   ├── test_versioning.py # Lineage, duplicate check, and transactional cascade tests
│   ├── test_orchestrator.py # End-to-end ingestion workflow tests
│   └── test_end_to_end_validation.py # Full validation suite with synthetic documents
├── requirements.txt       # Dependencies
├── ROADMAP.md             # Sequential phase tracking
└── README.md
```

---

## Intermediate `ParsedDocument` Object

The intermediate `ParsedDocument` contains raw document text mapped to its structural elements:

* **`file_path`**: Source path or URI.
* **`file_type`**: Detected format (`pdf`, `docx`, `md`, `txt`).
* **`title`**: Primary title extracted from document header or style.
* **`raw_text`**: Complete reconstructed textual content.
* **`elements`**: Chronological sequence of `StructuralElement` objects:
  * `element_type`: `TITLE`, `HEADING_1`, `HEADING_2`, `HEADING_3`, `PARAGRAPH`, `TABLE`
  * `content`: Text or markdown representation
  * `page_number`: 1-indexed physical page number
  * `heading_hierarchy`: Breadcrumbs of ancestor headings (e.g. `["1. Policies", "1.2 Travel"]`)
  * `metadata`: Font sizes, bounding boxes, or table dimensions
* **`tables`**: List of `ParsedTable` objects containing:
  * `markdown`: Formatted GitHub-flavored markdown table (`|---|---|`)
  * `headers`: Extracted column names
  * `rows`: 2D list of cell strings
  * `page_number`: Physical page containing the table
* **`total_pages`**: Total page count.
* **`success`**: `True` if parsed without crashing, `False` on corrupted/malformed input.
* **`error_message`**: Logged failure message if unrecoverable.

---

## Format Parsers

1. **PDF (`PDFParser`)**:
   * Uses **PyMuPDF** (`pymupdf`) for layout analysis, font-size distribution clustering (estimating base body text vs. headings), and native table detection (`page.find_tables()`).
   * Seamlessly integrates **Docling** for deep layout parsing when specified or installed.
   * Avoids table text duplication by subtracting table bounding boxes from text block extraction.
2. **DOCX (`DocxParser`)**:
   * Inspects Word styles (`Title`, `Heading 1`, `Heading 2`, `Heading 3`).
   * Extracts cell matrices from `docx.table.Table` into clean Markdown grids.
   * Tracks hard and rendered page breaks (`w:lastRenderedPageBreak`).
3. **Markdown (`MarkdownParser`)**:
   * Tracks `#`, `##`, and `###` headers.
   * Extracts markdown tables and tracks page breaks (`<!-- Page X -->`, `\newpage`).
4. **Text (`TextParser`)**:
   * Heuristic heading detection (underlined `====`/`----`, numbered `1.1`, or uppercase headers).
   * Page separation via ASCII form feeds (`\f`).

---

## Defensive Error Handling
All parsers inherit from `BaseParser.parse()`:
* Missing files or corrupted streams are caught, logged with full tracebacks, and return `ParsedDocument(success=False, error_message=...)` without terminating the host process.
