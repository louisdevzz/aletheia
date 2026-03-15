"""
Tool Registry

Manages tool registration and execution.
"""

from typing import Dict, List, Optional, Any
import asyncio
from .base import Tool, ToolCall, ToolResult


class ToolRegistry:
    """Registry for managing tools."""

    def __init__(self):
        self._tools: Dict[str, Tool] = {}

    def register(self, tool: Tool) -> "ToolRegistry":
        """Register a tool."""
        self._tools[tool.name] = tool
        return self

    def unregister(self, name: str) -> "ToolRegistry":
        """Unregister a tool."""
        self._tools.pop(name, None)
        return self

    def get(self, name: str) -> Optional[Tool]:
        """Get a tool by name."""
        return self._tools.get(name)

    def list_tools(self) -> List[str]:
        """List all registered tool names."""
        return list(self._tools.keys())

    def get_all_specs(self) -> List[Dict[str, Any]]:
        """Get all tool specifications."""
        return [tool.to_openai_function() for tool in self._tools.values()]

    async def execute(self, call: ToolCall) -> ToolResult:
        """
        Execute a tool call.

        Args:
            call: ToolCall to execute

        Returns:
            ToolResult from execution
        """
        tool = self.get(call.name)
        if not tool:
            return ToolResult(
                success=False, output="", error=f"Tool '{call.name}' not found"
            )

        try:
            return await tool.execute(call.arguments)
        except Exception as e:
            return ToolResult(
                success=False, output="", error=f"Error executing tool: {str(e)}"
            )

    async def execute_many(self, calls: List[ToolCall]) -> List[ToolResult]:
        """
        Execute multiple tool calls in parallel.

        Args:
            calls: List of ToolCalls

        Returns:
            List of ToolResults
        """
        tasks = [self.execute(call) for call in calls]
        return await asyncio.gather(*tasks)
