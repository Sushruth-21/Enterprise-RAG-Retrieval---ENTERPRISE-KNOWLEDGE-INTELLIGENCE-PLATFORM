import logging
import time
from pathlib import Path
from typing import Any, List, Optional, Union

import numpy as np
from PIL import Image

from .models import OCRResult

logger = logging.getLogger("document_intelligence.ocr.offline")

_RAPIDOCR_INSTANCE = None


def get_rapidocr_engine():
    """Lazily initialize the singleton RapidOCR engine."""
    global _RAPIDOCR_INSTANCE
    if _RAPIDOCR_INSTANCE is None:
        try:
            from rapidocr import RapidOCR
            # RapidOCR uses ONNXRuntime under the hood with lightweight PP-OCR models
            _RAPIDOCR_INSTANCE = RapidOCR()
            logger.info("RapidOCR offline engine initialized with ONNX Runtime.")
        except Exception as e:
            logger.error(f"Failed to initialize RapidOCR engine: {e}")
            raise
    return _RAPIDOCR_INSTANCE


class OfflineRapidOCR:
    """
    Ultra-fast, fully offline OCR engine running via ONNXRuntime.
    No external system binaries (like Tesseract.exe) required.
    Typical latency: 25ms - 75ms per image.
    """

    def __init__(self):
        self.engine = get_rapidocr_engine()

    def process_image(self, image_input: Union[str, Path, bytes, Image.Image, np.ndarray]) -> OCRResult:
        """
        Executes offline OCR on an image.
        :param image_input: File path, raw bytes, PIL Image, or numpy array.
        :returns: OCRResult containing text, lines, bounding boxes, and average confidence.
        """
        start_time = time.perf_counter()
        img_array = self._normalize_image_to_numpy(image_input)

        out = self.engine(img_array)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if not out or not getattr(out, "txts", None):
            return OCRResult(
                text="",
                confidence=0.0,
                engine_used="rapidocr_offline",
                lines=[],
                scores=[],
                boxes=[],
                duration_ms=duration_ms,
                fallback_triggered=False,
            )

        raw_txts = list(out.txts)
        raw_scores = [float(s) for s in getattr(out, "scores", [])]
        raw_boxes = [b.tolist() if hasattr(b, "tolist") else b for b in getattr(out, "boxes", [])]

        avg_confidence = float(np.mean(raw_scores)) if raw_scores else 0.0

        # Try to use built-in markdown formatting if available, or reconstruct paragraphs
        formatted_text = ""
        if hasattr(out, "to_markdown") and callable(out.to_markdown):
            try:
                formatted_text = out.to_markdown()
            except Exception:
                pass

        if not formatted_text:
            formatted_text = "\n".join(raw_txts).strip()

        logger.info(
            f"[Offline OCR] Extracted {len(raw_txts)} lines | Avg Confidence: {avg_confidence:.2%} "
            f"| Latency: {duration_ms}ms"
        )

        return OCRResult(
            text=formatted_text,
            confidence=round(avg_confidence, 4),
            engine_used="rapidocr_offline",
            lines=raw_txts,
            scores=[round(s, 4) for s in raw_scores],
            boxes=raw_boxes,
            duration_ms=duration_ms,
            fallback_triggered=False,
            metadata={"line_count": len(raw_txts)},
        )

    @staticmethod
    def _normalize_image_to_numpy(image_input: Any) -> np.ndarray:
        """Converts diverse image formats into an RGB NumPy array."""
        if isinstance(image_input, np.ndarray):
            return image_input
        elif isinstance(image_input, Image.Image):
            return np.array(image_input.convert("RGB"))
        elif isinstance(image_input, (str, Path)):
            pil_img = Image.open(str(image_input)).convert("RGB")
            return np.array(pil_img)
        elif isinstance(image_input, bytes):
            import io
            pil_img = Image.open(io.BytesIO(image_input)).convert("RGB")
            return np.array(pil_img)
        else:
            raise ValueError(f"Unsupported image input type: {type(image_input)}")
