import io
import pytest
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

from ocr import HybridOCREngine, OCRResult, OfflineRapidOCR, OnlineGeminiVisionOCR
from parsers import ImageParser, get_parser, parse_document


def create_synthetic_test_image(text: str = "ENTERPRISE KNOWLEDGE PLATFORM") -> Image.Image:
    """Creates a high-contrast synthetic image containing crisp text for OCR testing."""
    img = Image.new("RGB", (600, 150), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Draw dark black text
    draw.text((30, 50), text, fill=(0, 0, 0))
    return img


def test_offline_rapidocr_synthetic_image():
    """Verifies that Offline RapidOCR extracts text from image with high confidence."""
    engine = OfflineRapidOCR()
    img = create_synthetic_test_image("CONFIDENTIAL FINANCIAL REPORT 2026")

    result = engine.process_image(img)

    assert isinstance(result, OCRResult)
    assert result.engine_used == "rapidocr_offline"
    assert "CONFIDENTIAL" in result.text.upper() or "REPORT" in result.text.upper()
    assert result.confidence > 0.80
    assert result.duration_ms > 0
    assert len(result.lines) >= 1


def test_image_parser_integration(tmp_path: Path):
    """Verifies ImageParser converts standalone image file into ParsedDocument."""
    img_path = tmp_path / "executive_brief.png"
    img = create_synthetic_test_image("STRATEGIC ROADMAP FOR AI")
    img.save(img_path)

    parser = ImageParser(ocr_mode="offline_only")
    doc = parser.parse(img_path)

    assert doc.success is True
    assert doc.file_type == "png"
    assert len(doc.elements) >= 1
    assert any("STRATEGIC" in el.content.upper() or "ROADMAP" in el.content.upper() for el in doc.elements)


def test_factory_resolves_image_parser():
    """Verifies get_parser() resolves common image extensions to ImageParser."""
    for ext in ["png", "jpg", "jpeg", "tiff", "webp", "bmp"]:
        parser = get_parser(f"document.{ext}")
        assert isinstance(parser, ImageParser)


def test_hybrid_engine_mode_offline():
    """Verifies HybridOCREngine handles offline execution."""
    hybrid = HybridOCREngine(mode="offline_only")
    img = create_synthetic_test_image("SYSTEM ARCHITECTURE SPECIFICATION")
    res = hybrid.extract_text(img)

    assert res.engine_used == "rapidocr_offline"
    assert res.fallback_triggered is False
    assert len(res.text) > 0


def test_online_engine_missing_key():
    """Verifies Online Gemini engine raises clear ValueError when no API key is provided."""
    online = OnlineGeminiVisionOCR(api_key="")
    img = create_synthetic_test_image("SAMPLE TEST")

    with pytest.raises(ValueError, match="GEMINI_API_KEY is not set"):
        online.process_image(img)
