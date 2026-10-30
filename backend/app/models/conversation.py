from __future__ import annotations
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List


@dataclass
class ConversationMessage:
    role: str  # "user" | "assistant"
    content: str
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ConversationStore:
    """Thread-safe in-memory conversation store.
    Keeps the last MAX_MESSAGES messages per conversation (sliding window).
    """

    MAX_MESSAGES = 20

    def __init__(self) -> None:
        self._store: Dict[str, List[ConversationMessage]] = {}
        self._lock = asyncio.Lock()

    async def add_message(self, conversation_id: str, role: str, content: str) -> None:
        async with self._lock:
            if conversation_id not in self._store:
                self._store[conversation_id] = []
            self._store[conversation_id].append(
                ConversationMessage(role=role, content=content)
            )
            # Enforce sliding window
            if len(self._store[conversation_id]) > self.MAX_MESSAGES:
                self._store[conversation_id] = self._store[conversation_id][-self.MAX_MESSAGES :]

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
