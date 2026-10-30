from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import Optional

from app.config import Settings, get_settings

logger = logging.getLogger(__name__)


class CloudLLMClient(ABC):
    """Abstract base for all cloud LLM providers."""

    @abstractmethod
    async def generate(self, prompt: str, system: str = "", context: str = "") -> str: ...

    @abstractmethod
    async def is_available(self) -> bool: ...


# ──────────────────────────────────────────────────────────────
# Google Gemini
# ──────────────────────────────────────────────────────────────
class GeminiClient(CloudLLMClient):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = settings.CLOUD_MODEL_NAME

    async def generate(self, prompt: str, system: str = "", context: str = "") -> str:
        if not self.api_key:
            return ""
        try:
            import google.generativeai as genai  # type: ignore

            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.model_name,
                system_instruction=system or None,
            )
            full_prompt = f"Context:\n{context}\n\n{prompt}" if context else prompt
            response = await model.generate_content_async(
                full_prompt,
                generation_config={"temperature": 0.1, "max_output_tokens": 1024},
                request_options={"timeout": 30},
            )
            return response.text
        except Exception as exc:
            logger.error("Gemini error: %s", exc)
            return ""

    async def is_available(self) -> bool:
        return bool(self.api_key)


# ──────────────────────────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────────────────────────
class OpenAIClient(CloudLLMClient):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.model_name = settings.CLOUD_MODEL_NAME or "gpt-4o-mini"

    async def generate(self, prompt: str, system: str = "", context: str = "") -> str:
        if not self.api_key:
            return ""
        try:
            from openai import AsyncOpenAI  # type: ignore

            client = AsyncOpenAI(api_key=self.api_key, timeout=30)
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            if context:
                messages.append({"role": "user", "content": f"Context:\n{context}"})
            messages.append({"role": "user", "content": prompt})
            resp = await client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.1,
                max_tokens=1024,
            )
            return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.error("OpenAI error: %s", exc)
            return ""

    async def is_available(self) -> bool:
        return bool(self.api_key)


# ──────────────────────────────────────────────────────────────
# Anthropic Claude
# ──────────────────────────────────────────────────────────────
class AnthropicClient(CloudLLMClient):
    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.ANTHROPIC_API_KEY
        self.model_name = settings.CLOUD_MODEL_NAME or "claude-3-haiku-20240307"

    async def generate(self, prompt: str, system: str = "", context: str = "") -> str:
        if not self.api_key:
            return ""
        try:
            import anthropic  # type: ignore

            client = anthropic.AsyncAnthropic(api_key=self.api_key)
            full_prompt = f"Context:\n{context}\n\n{prompt}" if context else prompt
            msg = await client.messages.create(
                model=self.model_name,
                max_tokens=1024,
                system=system or "You are a helpful assistant.",
                messages=[{"role": "user", "content": full_prompt}],
            )
            return msg.content[0].text
        except Exception as exc:
            logger.error("Anthropic error: %s", exc)
            return ""

    async def is_available(self) -> bool:
        return bool(self.api_key)


# ──────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────
def get_cloud_client(settings: Optional[Settings] = None) -> CloudLLMClient:
    s = settings or get_settings()
    provider = s.CLOUD_PROVIDER.lower()
    if provider == "openai":
        return OpenAIClient(s)
    if provider == "anthropic":
        return AnthropicClient(s)
    return GeminiClient(s)  # default
