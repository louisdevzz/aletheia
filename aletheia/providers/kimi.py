"""
Kimi Provider
"""

import openai
import logging
from typing import Any, Dict
from ..config import kimi_config
from .base import Provider, ChatMessage, ChatRequest, ChatResponse

logger = logging.getLogger(__name__)


class KimiProvider(Provider):
    """Kimi (Moonshot) provider implementation."""

    def __init__(self, api_key: str = None, model: str = None):
        self.api_key = api_key or kimi_config.api_key
        self.model = model or kimi_config.model
        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=kimi_config.base_url,
            default_headers={"User-Agent": kimi_config.user_agent},
        )

    @property
    def name(self) -> str:
        return "kimi"

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Generate chat completion via Kimi."""
        messages = []
        for msg in request.messages:
            if msg.role == "assistant" and msg.tool_calls:
                # Assistant message with tool calls
                assistant_msg = {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": tc["arguments"],
                            },
                        }
                        for tc in (msg.tool_calls or [])
                    ],
                }
                # Add reasoning_content for Kimi's thinking mode (required when tool_calls present)
                # reasoning_content should contain the model's thinking process
                reasoning = f"I need to use the {msg.tool_calls[0]['name'] if msg.tool_calls else 'tool'} tool to help answer the user's question."
                assistant_msg["reasoning_content"] = reasoning
                messages.append(assistant_msg)
            elif msg.role == "tool":
                # Tool response message
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": msg.tool_call_id,
                        "content": msg.content,
                    }
                )
            else:
                # Regular message
                messages.append({"role": msg.role, "content": msg.content})

        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": request.temperature,
        }

        if request.tools:
            kwargs["tools"] = request.tools
            kwargs["tool_choice"] = request.tool_choice or "auto"
            tool_names = [
                t.get("function", {}).get("name", "unknown") for t in request.tools
            ]
            logger.info(f"🛠️  Sending {len(request.tools)} tools to Kimi: {tool_names}")
        else:
            logger.info("📤 Sending request to Kimi (no tools)")

        logger.info(
            f"📋 Messages count: {len(messages)}, Last message: {messages[-1]['content'][:80] if messages else 'N/A'}..."
        )

        response = self.client.chat.completions.create(**kwargs)

        has_tools = bool(response.choices[0].message.tool_calls)
        content_preview = (
            response.choices[0].message.content[:100]
            if response.choices[0].message.content
            else "None"
        )
        logger.info(
            f"📥 Kimi response: has_tools={has_tools}, content_preview={content_preview}..."
        )

        text = None
        if response.choices[0].message.content:
            text = response.choices[0].message.content

        tool_calls = []
        if (
            hasattr(response.choices[0].message, "tool_calls")
            and response.choices[0].message.tool_calls
        ):
            for tc in response.choices[0].message.tool_calls:
                tool_calls.append(
                    {
                        "id": tc.id,
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    }
                )

        return ChatResponse(
            text=text,
            tool_calls=tool_calls if tool_calls else None,
            usage={
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens
                if response.usage
                else 0,
            }
            if response.usage
            else None,
            raw_response=response,
        )
