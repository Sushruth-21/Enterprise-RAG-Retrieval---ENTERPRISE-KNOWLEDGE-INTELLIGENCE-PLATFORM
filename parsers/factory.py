import logging
from pathlib import Path
from typing import Dict, Optional, Type, Union

from .base import BaseParser
from .docx_parser import DocxParser
from .markdown_parser import MarkdownParser
from .models import ParsedDocument
from .pdf_parser import PDFParser
from .text_parser import TextParser

logger = logging.getLogger("document_intelligence.parsers")

# Registry mapping extensions to parser classes
PARSER_REGISTRY: Dict[str, Type[BaseParser]] = {
    "pdf": PDFParser,
    "docx": DocxParser,
    "md": MarkdownParser,
    "markdown": MarkdownParser,
    "txt": TextParser,
    "text": TextParser,
    "log": TextParser,
}


def get_parser(file_path_or_extension: Union[str, Path], **parser_kwargs) -> BaseParser:
    """
    Factory function returning the appropriate parser instance based on file extension.
    Falls back to TextParser for generic plain-text formats.
    """
    if isinstance(file_path_or_extension, Path):
        ext = file_path_or_extension.suffix.lower().lstrip(".")
    else:
        path = Path(file_path_or_extension)
        ext = path.suffix.lower().lstrip(".") if "." in file_path_or_extension else file_path_or_extension.lower().lstrip(".")

    parser_cls = PARSER_REGISTRY.get(ext)
    if not parser_cls:
        logger.warning(
            f"No specialized parser registered for extension '.{ext}'. Falling back to TextParser."
        )
        parser_cls = TextParser

    return parser_cls(**parser_kwargs)


def parse_document(file_path: Union[str, Path], **kwargs) -> ParsedDocument:
    """
    Convenience function to parse any supported document directly.
    Guarantees returning a ParsedDocument without throwing unhandled exceptions.
    """
    parser = get_parser(file_path, **kwargs)
    return parser.parse(file_path, **kwargs)
