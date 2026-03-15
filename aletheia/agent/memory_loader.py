"""
Memory Loader - Load context from memory system

Loads relevant memories with:
- Time decay (older memories score lower)
- Core category boost (durable facts/preferences)
- Over-fetch and re-ranking
"""

from typing import Dict, Any, List, Optional, Protocol
from dataclasses import dataclass
from datetime import datetime, timedelta
from abc import ABC, abstractmethod
import math


@dataclass
class MemoryEntry:
    """A memory entry."""

    id: str
    key: str
    content: str
    category: str  # "core", "conversation", "daily", etc.
    timestamp: str
    score: Optional[float] = None
    session_id: Optional[str] = None


class Memory(Protocol):
    """Protocol for memory systems."""

    async def recall(
        self, query: str, limit: int, session_id: Optional[str] = None
    ) -> List[MemoryEntry]:
        """Recall memories matching query."""
        ...

    async def store(
        self, key: str, content: str, category: str, session_id: Optional[str] = None
    ) -> None:
        """Store a memory."""
        ...


# Constants for memory loading
LOADER_DECAY_HALF_LIFE_DAYS = 7.0
CORE_CATEGORY_SCORE_BOOST = 0.3
RECALL_OVER_FETCH_FACTOR = 2


class MemoryLoader(ABC):
    """Abstract base class for memory loaders."""

    @abstractmethod
    async def load_context(self, memory: Memory, user_message: str) -> str:
        """
        Load memory context for a user message.

        Args:
            memory: Memory system
            user_message: Current user message

        Returns:
            Formatted context string
        """
        pass


class DefaultMemoryLoader(MemoryLoader):
    """
    Default memory loader with time decay and category boosting.

    Features:
    - Time decay: Older memories score lower (half-life 7 days)
    - Core boost: Core memories get +0.3 score boost
    - Over-fetch: Retrieve 2x limit for better ranking
    - Filtering: Skip assistant autosave entries
    """

    def __init__(self, limit: int = 5, min_relevance_score: float = 0.4):
        self.limit = max(1, limit)
        self.min_relevance_score = min_relevance_score

    async def load_context(self, memory: Memory, user_message: str) -> str:
        """
        Load memory context with decay and boosting.
        """
        # Over-fetch so Core-boosted entries can compete
        fetch_limit = self.limit * RECALL_OVER_FETCH_FACTOR
        entries = await memory.recall(user_message, fetch_limit, None)

        if not entries:
            return ""

        # Apply time decay
        self._apply_time_decay(entries, LOADER_DECAY_HALF_LIFE_DAYS)

        # Apply Core category boost and filter
        scored = []
        for entry in entries:
            # Skip assistant autosave entries
            if self._is_assistant_autosave_key(entry.key):
                continue

            base_score = entry.score or self.min_relevance_score
            boosted_score = self._apply_category_boost(entry, base_score)

            if boosted_score >= self.min_relevance_score:
                scored.append((entry, boosted_score))

        # Sort by boosted score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        scored = scored[: self.limit]

        if not scored:
            return ""

        # Format context
        context_lines = ["[Memory context]"]
        for entry, score in scored:
            context_lines.append(f"- {entry.key}: {entry.content}")

        return "\n".join(context_lines) + "\n"

    def _apply_time_decay(self, entries: List[MemoryEntry], half_life_days: float):
        """
        Apply exponential time decay to memory scores.

        Older memories get lower scores based on half-life.
        """
        now = datetime.now()

        for entry in entries:
            if entry.score is None:
                continue

            try:
                # Parse timestamp
                entry_time = datetime.fromisoformat(
                    entry.timestamp.replace("Z", "+00:00")
                )
                age_days = (now - entry_time).total_seconds() / (24 * 3600)

                # Apply exponential decay: score * (0.5 ^ (age / half_life))
                decay_factor = 0.5 ** (age_days / half_life_days)
                entry.score = entry.score * decay_factor

            except (ValueError, TypeError):
                # If can't parse timestamp, don't decay
                pass

    def _apply_category_boost(self, entry: MemoryEntry, base_score: float) -> float:
        """
        Apply score boost for Core category memories.

        Core memories (durable facts, preferences) get +0.3 boost.
        """
        if entry.category.lower() == "core":
            return min(1.0, base_score + CORE_CATEGORY_SCORE_BOOST)
        return base_score

    def _is_assistant_autosave_key(self, key: str) -> bool:
        """Check if key is a legacy assistant autosave entry."""
        return key.startswith("assistant_resp") or key.startswith("assistant_")


class SimpleMemoryLoader(MemoryLoader):
    """Simple memory loader without decay/boosting."""

    def __init__(self, limit: int = 5):
        self.limit = limit

    async def load_context(self, memory: Memory, user_message: str) -> str:
        """Simple loading without processing."""
        entries = await memory.recall(user_message, self.limit)

        if not entries:
            return ""

        context_lines = ["[Memory context]"]
        for entry in entries:
            context_lines.append(f"- {entry.key}: {entry.content}")

        return "\n".join(context_lines) + "\n"


class NoOpMemoryLoader(MemoryLoader):
    """Memory loader that returns empty context (disables memory)."""

    async def load_context(self, memory: Memory, user_message: str) -> str:
        return ""


def create_memory_loader(
    enable_decay: bool = True,
    enable_boost: bool = True,
    limit: int = 5,
    min_score: float = 0.4,
) -> MemoryLoader:
    """
    Factory function to create appropriate memory loader.

    Args:
        enable_decay: Enable time decay
        enable_boost: Enable category boosting
        limit: Maximum memories to load
        min_score: Minimum relevance score

    Returns:
        Configured MemoryLoader
    """
    if not enable_decay and not enable_boost:
        return SimpleMemoryLoader(limit)

    return DefaultMemoryLoader(limit, min_score)
