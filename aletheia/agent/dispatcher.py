"""
Tool Dispatcher - Handles LLM Function Calling

- Converts tool specs to OpenAI function format
- Parses LLM responses to extract tool calls
- Formats tool results back to LLM
"""

import json
from typing import Dict, Any, List, Optional, Tuple
from abc import ABC, abstractmethod

from aletheia.tools.base import ToolCall, ToolResult


class ToolDispatcher(ABC):
    """Abstract base for tool dispatchers."""

    @abstractmethod
    def to_provider_messages(
        self, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert internal history to provider format."""
        pass

    @abstractmethod
    def should_send_tool_specs(self) -> bool:
        """Whether to send tool specs to LLM."""
        pass

    @abstractmethod
    def parse_response(self, response: Any) -> Tuple[str, List[ToolCall]]:
        """
        Parse LLM response to extract text and tool calls.

        Returns:
            (text_content, list_of_tool_calls)
        """
        pass


class NativeToolDispatcher(ToolDispatcher):
    """
    Native OpenAI function calling dispatcher.

    Uses OpenAI's native function calling API.
    """

    def should_send_tool_specs(self) -> bool:
        return True

    def to_provider_messages(
        self, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert history to OpenAI message format."""
        messages = []
        for msg in history:
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                # Assistant message with tool calls
                messages.append(
                    {
                        "role": "assistant",
                        "content": msg.get("content", ""),
                        "tool_calls": msg["tool_calls"],
                    }
                )
            elif msg.get("role") == "tool":
                # Tool response message
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.get("tool_call_id"),
                        "content": msg.get("content", ""),
                    }
                )
            else:
                # Regular message
                messages.append(
                    {"role": msg.get("role", "user"), "content": msg.get("content", "")}
                )
        return messages

    def parse_response(self, response: Any) -> Tuple[str, List[ToolCall]]:
        """
        Parse OpenAI response.

        Args:
            response: OpenAI chat completion response

        Returns:
            (text_content, list_of_tool_calls)
        """
        text = ""
        tool_calls = []

        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message

            # Get text content
            if hasattr(message, "content") and message.content:
                text = message.content

            # Get tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tc in message.tool_calls:
                    if tc.type == "function":
                        try:
                            args = json.loads(tc.function.arguments)
                        except json.JSONDecodeError:
                            args = {}

                        tool_calls.append(
                            ToolCall(
                                name=tc.function.name, arguments=args, call_id=tc.id
                            )
                        )

        return text, tool_calls


class XmlToolDispatcher(ToolDispatcher):
    """
    XML-based tool dispatcher for providers without native function calling.

    Uses XML tags like <tool_call> for tool calls.
    """

    def should_send_tool_specs(self) -> bool:
        return False  # XML tools are described in system prompt

    def prompt_instructions(self, tools: List[Dict]) -> str:
        """Generate XML tool instructions for system prompt."""
        instructions = "\n\n## Tool Use Protocol\n\n"
        instructions += (
            "You can use tools by writing JSON inside \u003ctool_call\u003e tags:\n\n"
        )
        instructions += "\u003ctool_call\u003e\n"
        instructions += '{"name": "tool_name", "arguments": {"arg1": "value1"}}\n'
        instructions += "\u003c/tool_call\u003e\n\n"

        instructions += "Available tools:\n\n"
        for tool in tools:
            func = tool.get("function", {})
            name = func.get("name", "unknown")
            desc = func.get("description", "")
            instructions += f"- {name}: {desc}\n"

        return instructions

    def to_provider_messages(
        self, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Convert history - same format for XML."""
        return [
            {"role": msg.get("role", "user"), "content": msg.get("content", "")}
            for msg in history
        ]

    def parse_response(self, response: Any) -> Tuple[str, List[ToolCall]]:
        """
        Parse XML-style tool calls from response text.

        Format:
        \u003ctool_call>
        {"name": "tool_name", "arguments": {"arg1": "value1"}}
        \u003c/tool_call>
        """
        import re

        text = ""
        tool_calls = []

        if hasattr(response, "choices") and response.choices:
            text = response.choices[0].message.content or ""
        elif isinstance(response, str):
            text = response

        # Parse XML tool calls
        pattern = r"\u003ctool_call\u003e\s*(.*?)\s*\u003c/tool_call\u003e"
        matches = re.findall(pattern, text, re.DOTALL)

        for match in matches:
            try:
                data = json.loads(match.strip())
                name = data.get("name", "")
                args = data.get("arguments", {})
                if name:
                    tool_calls.append(ToolCall(name=name, arguments=args))
            except json.JSONDecodeError:
                continue

        # Remove tool calls from text
        clean_text = re.sub(pattern, "", text, flags=re.DOTALL).strip()

        return clean_text, tool_calls
