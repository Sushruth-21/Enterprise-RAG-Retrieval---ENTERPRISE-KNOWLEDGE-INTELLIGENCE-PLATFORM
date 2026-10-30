from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class ConversationMessage:
    role: str  # "user" | "assistant"
    content: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    coverage: str = "full"
    grounded_doc_count: int = 0
    execution_time_ms: int = 0
    citations: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    @property
    def created_at(self) -> str:
        return self.timestamp.isoformat()


class ConversationStore:
    """Thread-safe in-memory conversation store with sliding window."""

    MAX_MESSAGES = 50

    def __init__(self) -> None:
        self._store: Dict[str, List[ConversationMessage]] = {}
        self._lock = asyncio.Lock()

    async def add_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        coverage: str = "full",
        grounded_doc_count: int = 0,
        execution_time_ms: int = 0,
        citations: Optional[List[Dict[str, Any]]] = None,
    ) -> ConversationMessage:
        msg = ConversationMessage(
            role=role,
            content=content,
            conversation_id=conversation_id,
            coverage=coverage,
            grounded_doc_count=grounded_doc_count,
            execution_time_ms=execution_time_ms,
            citations=citations or [],
        )
        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append(msg)
            if len(self._store[conversation_id]) > self.MAX_MESSAGES:
                self._store[conversation_id] = self._store[conversation_id][-self.MAX_MESSAGES :]
        return msg

    async def get_history(self, conversation_id: str) -> List[ConversationMessage]:
        async with self._lock:
            return list(self._store.get(conversation_id, []))

    async def clear(self, conversation_id: str) -> None:
        async with self._lock:
            self._store.pop(conversation_id, None)

    async def get_context_string(self, conversation_id: str, max_turns: int = 6) -> str:
        """Format recent conversation history as a string for LLM context."""
        history = await self.get_history(conversation_id)
        recent = history[-max_turns:]
        lines = []
        for msg in recent:
            prefix = "User" if msg.role == "user" else "Assistant"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)


# Module-level singleton
conversation_store = ConversationStore()
