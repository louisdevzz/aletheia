"""
Tool Base Classes

Base classes for tool definitions.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from datetime import datetime
import json


@dataclass
class ToolSpec:
    """Tool specification for LLM function calling."""

    name: str
    description: str
    parameters: Dict[str, Any]


@dataclass
class ToolCall:
    """A tool call from LLM."""

    name: str
    arguments: Dict[str, Any]
    call_id: Optional[str] = None


@dataclass
class ToolResult:
    """Result from tool execution."""

    success: bool
    output: str
    error: Optional[str] = None
    timestamp: Optional[str] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()


class Tool(ABC):
    """Base class for all tools."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Tool name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Tool description."""
        pass

    @property
    def parameters_schema(self) -> Dict[str, Any]:
        """JSON schema for tool parameters."""
        return {"type": "object", "properties": {}, "required": []}

    def spec(self) -> ToolSpec:
        """Get tool specification."""
        return ToolSpec(
            name=self.name,
            description=self.description,
            parameters=self.parameters_schema,
        )

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> ToolResult:
        """
        Execute the tool.

        Args:
            arguments: Tool arguments from LLM

        Returns:
            ToolResult with execution results
        """
        pass

    def to_openai_function(self) -> Dict[str, Any]:
        """Convert to OpenAI function format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters_schema,
            },
        }
