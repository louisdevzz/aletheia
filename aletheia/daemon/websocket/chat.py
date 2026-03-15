"""
WebSocket Chat Handler

Protocol:
Client → Server:
    {"type": "chat.message", "payload": {"message": "...", "session_id": "...", "provider": "kimi"}}

Server → Client (streaming):
    {"type": "chat.chunk", "payload": {"content": "...", "done": false}}
    {"type": "chat.chunk", "payload": {"content": "", "done": true, "sources": []}}
"""

import json
import logging
from typing import Optional, Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from aletheia.agent import Agent
from aletheia.providers.kimi import KimiProvider

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

# Session storage: session_id -> agent
_sessions: Dict[str, Agent] = {}


def _chunk_msg(content: str, done: bool = False, sources: Optional[list] = None) -> str:
    """Serialize a chat.chunk message."""
    payload: dict = {"content": content, "done": done}
    if done and sources:
        payload["sources"] = sources
    return json.dumps({"type": "chat.chunk", "payload": payload})


def _error_msg(message: str) -> str:
    """Serialize an error message."""
    return json.dumps({"type": "error", "payload": {"message": message}})


def _create_agent(provider: str = "kimi") -> Agent:
    """Create a new agent with tools and dispatcher."""
    from aletheia.agent.agent import AgentConfig
    from aletheia.agent.dispatcher import NativeToolDispatcher
    from aletheia.tools.rag_tool import RAGTool
    from aletheia.tools.calculator_tool import CalculatorTool

    # Always use Kimi provider
    llm_provider = KimiProvider()

    # Create tools list
    tools = [RAGTool(), CalculatorTool()]

    # Create dispatcher
    dispatcher = NativeToolDispatcher()

    # Create config
    config = AgentConfig(
        max_iterations=5,
        temperature=0.7,
        enable_research=True,
        enable_loop_detection=True,
    )

    return Agent(
        provider=llm_provider,
        tools=tools,
        dispatcher=dispatcher,
        config=config,
    )


def _get_or_create_agent(session_id: str, provider: str = "kimi") -> Agent:
    """Get existing agent or create new one for session."""
    if session_id not in _sessions:
        logger.info(
            "Creating new agent for session %s (provider=%s)", session_id[:8], provider
        )
        _sessions[session_id] = _create_agent(provider=provider)
    return _sessions[session_id]


@router.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """
    WebSocket endpoint for chat with function calling.
    """
    await websocket.accept()
    connection_id = id(websocket)
    logger.info("[%s] WebSocket connected", connection_id)

    try:
        while True:
            # Receive message
            raw = await websocket.receive_text()

            # Parse frame
            try:
                frame = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(_error_msg("Invalid JSON"))
                continue

            if frame.get("type") != "chat.message":
                await websocket.send_text(_error_msg("Expected 'chat.message' type"))
                continue

            payload = frame.get("payload", {})
            user_message = payload.get("message", "").strip()
            session_id = payload.get("session_id", str(connection_id))
            provider = payload.get("provider", "kimi")

            if not user_message:
                await websocket.send_text(_error_msg("Message cannot be empty"))
                continue

            logger.info(
                "[%s] Message: %r (session=%s, provider=%s)",
                connection_id,
                user_message[:50],
                session_id[:8],
                provider,
            )

            # Get or create agent
            agent = _get_or_create_agent(session_id, provider)

            # Get response
            try:
                response = await agent.chat(user_message)
                await websocket.send_text(_chunk_msg(content=response, done=False))
                # Send done frame
                await websocket.send_text(_chunk_msg(content="", done=True))

            except Exception as exc:
                logger.error("[%s] Agent error: %s", connection_id, exc)
                await websocket.send_text(_error_msg(f"Error: {str(exc)}"))

    except WebSocketDisconnect:
        logger.info("[%s] Client disconnected", connection_id)
    except Exception as exc:
        logger.error("[%s] Unexpected error: %s", connection_id, exc)
