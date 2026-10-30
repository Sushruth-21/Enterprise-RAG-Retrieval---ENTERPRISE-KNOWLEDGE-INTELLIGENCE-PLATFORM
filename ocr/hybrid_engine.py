import logging
import os
from pathlib import Path
from typing import Any, Optional, Union
from PIL import Image

from .models import OCRResult
from .offline_engine import OfflineRapidOCR
from .online_engine import OnlineGeminiVisionOCR

logger = logging.getLogger("document_intelligence.ocr.hybrid")


class HybridOCREngine:
    """
    Intelligent Hybrid OCR Engine:
    - Primary: High-speed, self-contained offline OCR (RapidOCR / ONNXRuntime) in ~40ms.
    - Fail-Safe: Cloud Multimodal Vision (Gemini 2.0 Flash) triggered when confidence < threshold
      or when offline parsing fails.
    """

    def __init__(
        self,
        mode: str = "auto",
        confidence_threshold: float = 0.65,
        gemini_api_key: Optional[str] = None,
    ):
        """
        :param mode: 'auto' (hybrid with fail-safe), 'offline_only', or 'online_only'.
        :param confidence_threshold: Float [0.0-1.0]. If offline confidence is below this,
               fail-safe online OCR is triggered automatically.
        """
        enable_cloud = os.getenv("ENABLE_CLOUD_FALLBACK", "false").lower() in ("true", "1")
        if not enable_cloud:
            self.mode = "offline_only"
            self.gemini_api_key = ""
        else:
            self.mode = mode.lower()
            self.gemini_api_key = gemini_api_key or os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""

        self.confidence_threshold = confidence_threshold
        self.offline_engine = OfflineRapidOCR()
        self._online_engine: Optional[OnlineGeminiVisionOCR] = None

    @property
    def online_engine(self) -> OnlineGeminiVisionOCR:
        if self._online_engine is None:
            self._online_engine = OnlineGeminiVisionOCR(api_key=self.gemini_api_key)
        return self._online_engine

    def extract_text(self, image_input: Union[str, Path, bytes, Image.Image]) -> OCRResult:
        """
        Extracts text from an image using the hybrid strategy.
        """
        if self.mode == "online_only":
            logger.info("[OCR] Running in online_only mode (Gemini Vision).")
            return self.online_engine.process_image(image_input)

        # 1. Run Fast Offline Engine
        try:
            offline_result = self.offline_engine.process_image(image_input)
        except Exception as e:
            logger.warning(f"[OCR] Offline engine crashed: {e}")
            offline_result = OCRResult(
                text="",
                confidence=0.0,
                engine_used="rapidocr_offline",
            )

        # 2. Check Fail-Safe Criteria
        should_fallback = False
        fallback_reason = ""

        if self.mode == "auto":
            if not offline_result.text.strip():
                should_fallback = True
                fallback_reason = "No text detected by offline OCR"
            elif offline_result.confidence < self.confidence_threshold:
                should_fallback = True
                fallback_reason = (
                    f"Low confidence ({offline_result.confidence:.2%}) "
                    f"below threshold ({self.confidence_threshold:.2%})"
                )

        # 3. Trigger Fail-Safe if needed and API key is present
        if should_fallback:
            if self.gemini_api_key:
                logger.warning(
                    f"[OCR FAIL-SAFE ENGAGED] {fallback_reason}. "
                    f"Falling back to Gemini 2.0 Flash Vision..."
                )
                try:
                    online_result = self.online_engine.process_image(image_input)
                    online_result.fallback_triggered = True
                    online_result.metadata["offline_confidence"] = offline_result.confidence
                    online_result.metadata["fallback_reason"] = fallback_reason
                    return online_result
                except Exception as e:
                    logger.error(f"[OCR Fail-Safe Failed] Gemini Vision error: {e}. Returning offline result.")
            else:
                logger.info(
                    f"[OCR Fail-Safe Skipped] {fallback_reason}, but GEMINI_API_KEY not configured. "
                    f"Returning offline result."
                )

        return offline_result
