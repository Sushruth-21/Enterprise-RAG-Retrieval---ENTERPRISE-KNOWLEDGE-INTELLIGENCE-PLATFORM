from __future__ import annotations
import logging
from typing import List

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)


class OllamaClient:
    """Async HTTP client for Ollama local inference."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.OLLAMA_BASE_URL.rstrip("/")
        self.model = settings.OLLAMA_MODEL
        self.timeout = settings.OLLAMA_TIMEOUT

    async def generate(self, prompt: str, system: str = "", context: str = "") -> str:
        """Single-turn generation. Returns empty string on failure."""
        full_prompt = ""
        if context:
            full_prompt += f"Context:\n{context}\n\n"
        full_prompt += prompt

        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "system": system,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                resp.raise_for_status()
                return resp.json().get("response", "")
        except httpx.ConnectError:
            logger.warning("Ollama not reachable at %s", self.base_url)
            return ""
        except httpx.TimeoutException:
            logger.warning("Ollama timed out after %ds", self.timeout)
            return ""
        except Exception as exc:
            logger.error("Ollama generate error: %s", exc)
            return ""

    async def chat(self, messages: List[dict]) -> str:
        """Multi-turn chat. messages = [{"role": "user"|"assistant", "content": "..."}]"""
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 1024},
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                resp.raise_for_status()
                return resp.json().get("message", {}).get("content", "")
        except httpx.ConnectError:
            logger.warning("Ollama not reachable at %s", self.base_url)
            return ""
        except Exception as exc:
            logger.error("Ollama chat error: %s", exc)
            return ""

    async def is_available(self) -> bool:
        """Check if Ollama is running and has the configured model."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                models = [m["name"] for m in resp.json().get("models", [])]
                return any(self.model in m for m in models)
        except Exception:
            return False

    async def list_models(self) -> List[str]:
        """List all available Ollama models."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                return [m["name"] for m in resp.json().get("models", [])]
        except Exception:
            return []
