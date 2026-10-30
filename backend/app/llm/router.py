from __future__ import annotations
import logging
from typing import Literal, Optional, Tuple

from app.config import get_settings
from app.llm.ollama_client import OllamaClient
from app.llm.cloud_client import get_cloud_client

logger = logging.getLogger(__name__)

# Keywords that suggest a query needs more power (cloud preferred)
COMPLEX_QUERY_SIGNALS = [
    "compare all", "summarize all", "list every", "across all documents",
    "overview of all", "enumerate", "comprehensive", "entire policy",
]

# Scope that must stay local (confidential data never goes to cloud)
CONFIDENTIAL_SCOPES = {"confidential", "restricted", "internal"}


class ModelRouter:
    """Decides whether a query goes to local Ollama or the cloud LLM."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self.ollama = OllamaClient()
        self.cloud = get_cloud_client(self.settings)

    async def route(
        self,
        question: str,
        access_scope: str = "public",
        force_local: Optional[bool] = None,
    ) -> Literal["local", "cloud"]:
        """Return routing decision without generating a response."""
        # Hard rules first
        if force_local is True:
            return "local"
        if access_scope.lower() in CONFIDENTIAL_SCOPES:
            logger.info("Routing to local: confidential scope")
            return "local"

        # Check for complex query signals → prefer cloud
        q_lower = question.lower()
        if any(sig in q_lower for sig in COMPLEX_QUERY_SIGNALS):
            if self.settings.ENABLE_CLOUD_FALLBACK and await self.cloud.is_available():
                logger.info("Routing to cloud: complex query signal")
                return "cloud"

        # Rough token estimate (1 token ≈ 0.75 words)
        estimated_tokens = len(question.split()) * 1.3
        if estimated_tokens > 500:
            if self.settings.ENABLE_CLOUD_FALLBACK and await self.cloud.is_available():
                logger.info("Routing to cloud: long query (%d est. tokens)", estimated_tokens)
                return "cloud"

        # Default: prefer local
        if await self.ollama.is_available():
            logger.info("Routing to local: Ollama available")
            return "local"

        # Fallback to cloud
        if self.settings.ENABLE_CLOUD_FALLBACK and await self.cloud.is_available():
            logger.info("Routing to cloud: Ollama unavailable, using fallback")
            return "cloud"

        # Neither available — return local and let the caller handle the empty response
        logger.error("No AI backend available (Ollama down, cloud not configured)")
        return "local"

    async def generate(
        self,
        question: str,
        system_prompt: str,
        context: str,
        access_scope: str = "public",
        force_local: Optional[bool] = None,
    ) -> Tuple[str, str]:
        """Route then generate. Returns (answer_text, model_name_label)."""
        decision = await self.route(question, access_scope, force_local)

        if decision == "local":
            answer = await self.ollama.generate(
                prompt=question, system=system_prompt, context=context
            )
            model_label = f"{self.settings.OLLAMA_MODEL} (local)"
            if not answer:
                # Try cloud as emergency fallback (only if scope allows)
                if (
                    self.settings.ENABLE_CLOUD_FALLBACK
                    and access_scope.lower() not in CONFIDENTIAL_SCOPES
                    and await self.cloud.is_available()
                ):
                    logger.warning("Ollama returned empty, falling back to cloud")
                    answer = await self.cloud.generate(question, system_prompt, context)
                    model_label = f"{self.settings.CLOUD_MODEL_NAME} (cloud-fallback)"
        else:
            answer = await self.cloud.generate(
                prompt=question, system=system_prompt, context=context
            )
            model_label = f"{self.settings.CLOUD_MODEL_NAME} (cloud)"
            if not answer:
                # Try local as emergency fallback
                logger.warning("Cloud returned empty, falling back to Ollama")
                answer = await self.ollama.generate(question, system_prompt, context)
                model_label = f"{self.settings.OLLAMA_MODEL} (local-fallback)"

        return answer or "I was unable to generate a response at this time.", model_label
