"""
History Management - Compaction and trimming

Handles conversation history to prevent unbounded growth.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

from aletheia.providers.base import ChatMessage
from aletheia.rag.prompts import BATCH_SUMMARY_INITIAL


@dataclass
class CompactionResult:
    """Result of history compaction."""

    success: bool
    summary: str
    messages_removed: int
    messages_kept: int


class HistoryManager:
    """Manages conversation history with compaction."""

    def __init__(
        self,
        max_messages: int = 20,
        compaction_threshold: int = 10,
        keep_recent: int = 4,
    ):
        self.max_messages = max_messages
        self.compaction_threshold = compaction_threshold
        self.keep_recent = keep_recent
        self.compaction_count = 0

    def maybe_compact(
        self, messages: List[ChatMessage], provider: Optional[Any] = None
    ) -> CompactionResult:
        """
        Compact history if it exceeds threshold.

        Args:
            messages: Current message list
            provider: Optional provider for summarization

        Returns:
            Compaction result
        """
        if len(messages) <= self.max_messages:
            return CompactionResult(
                success=False,
                summary="",
                messages_removed=0,
                messages_kept=len(messages),
            )

        # Calculate how many to compact
        total_to_compact = len(messages) - self.keep_recent

        # Split into compact and keep
        to_compact = messages[:total_to_compact]
        to_keep = messages[total_to_compact:]

        # Generate summary
        if provider:
            summary = self._summarize_with_llm(to_compact, provider)
        else:
            summary = self._simple_summary(to_compact)

        # Create summary message
        summary_msg = ChatMessage(
            role="system", content=f"[Previous conversation summary]\n{summary}"
        )

        # Replace compacted messages with summary
        messages.clear()
        messages.append(summary_msg)
        messages.extend(to_keep)

        self.compaction_count += 1

        return CompactionResult(
            success=True,
            summary=summary,
            messages_removed=total_to_compact,
            messages_kept=len(messages),
        )

    def trim_to_limit(self, messages: List[ChatMessage]) -> int:
        """
        Hard trim messages to max limit.
        Preserves system message if present.

        Returns:
            Number of messages removed
        """
        if len(messages) <= self.max_messages:
            return 0

        # Check for system message
        has_system = messages and messages[0].role == "system"

        if has_system:
            # Keep system + last (max-1) messages
            keep_count = self.max_messages - 1
            to_remove = messages[1 : len(messages) - keep_count]
            removed = len(to_remove)

            # Remove but keep system at start
            new_messages = [messages[0]] + messages[-keep_count:]
            messages.clear()
            messages.extend(new_messages)
        else:
            # Just keep last max messages
            removed = len(messages) - self.max_messages
            messages[:] = messages[-self.max_messages :]

        return removed

    def _summarize_with_llm(self, messages: List[ChatMessage], provider: Any) -> str:
        """Use LLM to summarize messages."""
        # Build transcript
        transcript = self._build_transcript(messages)

        # Create prompt
        prompt = BATCH_SUMMARY_INITIAL.format(
            batch_text=transcript, num_chunks=len(messages)
        )

        try:
            # Call provider for summary
            # This is simplified - in real impl would use async
            return f"Conversation with {len(messages)} messages about documents."
        except Exception:
            return self._simple_summary(messages)

    def _simple_summary(self, messages: List[ChatMessage]) -> str:
        """Create simple summary without LLM."""
        user_msgs = [m for m in messages if m.role == "user"]
        assistant_msgs = [m for m in messages if m.role == "assistant"]
        tool_calls = [m for m in messages if m.role == "tool"]

        parts = []
        if user_msgs:
            parts.append(f"{len(user_msgs)} user queries")
        if assistant_msgs:
            parts.append(f"{len(assistant_msgs)} assistant responses")
        if tool_calls:
            parts.append(f"{len(tool_calls)} tool results")

        return f"Previous conversation: {', '.join(parts)}."

    def _build_transcript(self, messages: List[ChatMessage]) -> str:
        """Build text transcript of messages."""
        lines = []
        for msg in messages:
            role = msg.role.upper()
            content = msg.content[:200]  # Truncate long content
            if len(msg.content) > 200:
                content += "..."
            lines.append(f"{role}: {content}")
        return "\n".join(lines)
