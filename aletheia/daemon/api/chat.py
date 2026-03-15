"""
Chat API Routes

Streaming chat and WebSocket endpoints
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, AsyncGenerator
import asyncio
import json

from aletheia.agent import Agent
from aletheia.rag.storage import get_storage

router = APIRouter(tags=["chat"])

# Global agent instance
_agent: Optional[Agent] = None


def get_agent() -> Agent:
    """Get or create agent instance."""
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    stream: bool = True


class ChatMessage(BaseModel):
    role: str
    content: str
    sources: Optional[List[dict]] = None


class ChatHistoryResponse(BaseModel):
    messages: List[ChatMessage]
    session_id: str


async def generate_stream(message: str) -> AsyncGenerator[str, None]:
    """
    Generate streaming response from agent.

    Args:
        message: User message

    Yields:
        SSE formatted strings
    """
    agent = get_agent()

    try:
        async for chunk in agent.process(message):
            # SSE format
            data = json.dumps({"content": chunk})
            yield f"data: {data}\n\n"

        # End of stream
        yield f"data: {json.dumps({'done': True})}\n\n"

    except Exception as e:
        error_data = json.dumps({"error": str(e)})
        yield f"data: {error_data}\n\n"


@router.post("/chat")
async def chat(request: ChatRequest):
    """
    Send a chat message.

    Returns streaming response by default.
    """
    if not request.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty")

    if request.stream:
        return StreamingResponse(
            generate_stream(request.message), media_type="text/event-stream"
        )
    else:
        # Non-streaming response
        agent = get_agent()
        chunks = []
        async for chunk in agent.process(request.message):
            chunks.append(chunk)
        return {"content": "".join(chunks)}


@router.get("/chat/history/{session_id}", response_model=ChatHistoryResponse)
async def get_chat_history(session_id: str):
    """
    Get chat history for a session.
    """
    try:
        storage = get_storage()
        history = storage.get_chat_history(session_id)

        messages = [
            ChatMessage(
                role=msg["role"], content=msg["content"], sources=msg.get("sources")
            )
            for msg in history
        ]

        return ChatHistoryResponse(messages=messages, session_id=session_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
