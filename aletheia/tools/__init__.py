"""
Aletheia Tools - Tool system for Agent.

This package contains the tool infrastructure:
- base: Tool base class
- registry: Tool registry for managing tools
- rag_tool: RAG tool wrapper
- calculator_tool: Calculator tool
"""

from .base import Tool, ToolSpec, ToolCall, ToolResult
from .registry import ToolRegistry
from .rag_tool import RAGTool
from .calculator_tool import CalculatorTool

__all__ = [
    "Tool",
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ToolRegistry",
    "RAGTool",
    "CalculatorTool",
]
