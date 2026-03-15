"""
Agent Loop - Tool Call Loop Implementation

Comprehensive loop management for agent tool execution.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import time
import json

from aletheia.tools.base import Tool, ToolCall, ToolResult
from aletheia.tools.registry import ToolRegistry
from aletheia.providers.base import Provider, ChatMessage, ChatRequest, ChatResponse


@dataclass
class LoopContext:
    """Context maintained throughout the agent loop."""

    messages: List[ChatMessage] = field(default_factory=list)
    tool_calls_history: List[Dict] = field(default_factory=list)
    iteration_count: int = 0
    max_iterations: int = 5
    start_time: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, **kwargs):
        """Add a message to the conversation."""
        msg = ChatMessage(role=role, content=content, **kwargs)
        self.messages.append(msg)

    def add_tool_call(self, name: str, arguments: Dict, result: ToolResult):
        """Record a tool call with its result."""
        self.tool_calls_history.append(
            {
                "name": name,
                "arguments": arguments,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
        )

    def get_elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return (time.time() - self.start_time) * 1000


@dataclass
class LoopConfig:
    """Configuration for the agent loop."""

    max_iterations: int = 5
    max_history_messages: int = 20
    enable_loop_detection: bool = True
    enable_auto_compaction: bool = True
    compaction_threshold: int = 10
    tool_timeout_seconds: float = 30.0
    temperature: float = 0.7
