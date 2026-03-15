"""
Provider Base Classes

LLM provider abstraction layer.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    """A chat message."""

    role: str  # "system", "user", "assistant", "tool"
    content: str
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None


@dataclass
class ChatRequest:
    """Request for chat completion."""

    messages: List[ChatMessage]
    tools: Optional[List[Dict]] = None
    tool_choice: Optional[str] = None
    temperature: float = 0.7
    stream: bool = False


@dataclass
class ChatResponse:
    """Response from chat completion."""

    text: Optional[str]
    tool_calls: List[Dict] = None
    usage: Optional[Dict] = None
    raw_response: Any = None


class Provider(ABC):
    """Abstract base class for LLM providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        pass

    @abstractmethod
    async def chat(self, request: ChatRequest) -> ChatResponse:
        """
        Generate chat completion.

        Args:
            request: Chat request with messages and optional tools

        Returns:
            ChatResponse with text and/or tool calls
        """
        pass
