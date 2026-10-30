import base64
import io
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional, Union

import httpx
from PIL import Image

from .models import OCRResult

logger = logging.getLogger("document_intelligence.ocr.online")


class OnlineGeminiVisionOCR:
    """
    High-fidelity fail-safe cloud OCR engine using Google Gemini 2.0 Flash Multimodal Vision.
    
    Why Gemini Vision for the Fail-Safe:
    - Superior extraction on severely degraded scans, distorted receipts, handwritten notes, and complex multi-column tables.
    - Native Markdown table formatting output directly from image pixels.
    - Uses the same GEMINI_API_KEY already configured in Person 1's architecture.
    """

    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-2.0-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
        self.model = model
        self.endpoint = (
            f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent"
        )

    def process_image(self, image_input: Union[str, Path, bytes, Image.Image]) -> OCRResult:
        """
        Executes cloud vision OCR via Gemini 2.0 Flash REST API.
        """
        start_time = time.perf_counter()

        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY is not set. Online fail-safe OCR requires a valid Gemini API key."
            )

        b64_image, mime_type = self._encode_image_to_base64(image_input)

        prompt = (
            "You are an enterprise Optical Character Recognition (OCR) engine.\n"
            "Extract all readable text, titles, headings, and tables from this image with 100% accuracy.\n"
            "Rules:\n"
            "1. Output valid GitHub-flavored Markdown tables for any tabular data detected.\n"
            "2. Preserve structural headings (#, ##, ###) and paragraph breaks.\n"
            "3. Do NOT summarize, explain, or invent information.\n"
            "4. Return ONLY the extracted document text content."
        )

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": b64_image,
                            }
                        },
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 4096,
            },
        }

        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    f"{self.endpoint}?key={self.api_key}",
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                response.raise_for_status()
                data = response.json()

            candidates = data.get("candidates", [])
            extracted_text = ""
            if candidates:
                parts = candidates[0].get("content", {}).get("parts", [])
                extracted_text = "".join(p.get("text", "") for p in parts).strip()

            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.info(
                f"[Online Gemini OCR] Extracted {len(extracted_text)} chars in {duration_ms}ms"
            )

            lines = [l for l in extracted_text.splitlines() if l.strip()]

            return OCRResult(
                text=extracted_text,
                confidence=0.98,  # Gemini Vision multimodal accuracy on text
                engine_used="gemini_vision_online",
                lines=lines,
                scores=[0.98] * len(lines),
                duration_ms=duration_ms,
                fallback_triggered=True,
                metadata={"model": self.model},
            )
        except Exception as e:
            logger.error(f"[Online Gemini OCR Failed] {str(e)}", exc_info=True)
            raise

    def _encode_image_to_base64(self, image_input: Any) -> tuple[str, str]:
        """Encodes diverse image inputs into Base64 string and MIME type."""
        if isinstance(image_input, (str, Path)):
            path = Path(image_input)
            ext = path.suffix.lower().lstrip(".")
            mime = f"image/{ext}" if ext in ("png", "jpeg", "jpg", "webp", "gif") else "image/jpeg"
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            return b64, mime
        elif isinstance(image_input, bytes):
            b64 = base64.b64encode(image_input).decode("utf-8")
            return b64, "image/jpeg"
        elif isinstance(image_input, Image.Image):
            buf = io.BytesIO()
            fmt = image_input.format or "PNG"
            image_input.save(buf, format=fmt)
            b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
            return b64, f"image/{fmt.lower()}"
        else:
            raise ValueError(f"Cannot encode image of type {type(image_input)}")
