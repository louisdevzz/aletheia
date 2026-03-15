"""
WebSocket Connection Manager

Handles multiple concurrent WebSocket connections, connection lifecycle,
and message broadcasting for future multi-user support.
"""
import asyncio
import json
import logging
from typing import Dict, Optional
from uuid import uuid4

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """
    Manages active WebSocket connections.

    Supports:
    - Multiple concurrent connections
    - Per-connection message sending
    - Broadcasting to all connections
    - Graceful disconnection handling
    """

    def __init__(self):
        # connection_id -> WebSocket
        self._connections: Dict[str, WebSocket] = {}

    @property
    def active_count(self) -> int:
        """Number of currently active connections."""
        return len(self._connections)

    def generate_connection_id(self) -> str:
        """Generate a unique connection ID."""
        return str(uuid4())

    async def connect(self, websocket: WebSocket, connection_id: Optional[str] = None) -> str:
        """
        Accept and register a new WebSocket connection.

        Args:
            websocket: The incoming WebSocket connection.
            connection_id: Optional explicit ID. A new UUID is generated if omitted.

        Returns:
            The connection ID assigned to this connection.
        """
        await websocket.accept()
        if connection_id is None:
            connection_id = self.generate_connection_id()
        self._connections[connection_id] = websocket
        logger.info("WebSocket connected: %s (total active: %d)", connection_id, self.active_count)
        return connection_id

    def disconnect(self, connection_id: str) -> None:
        """
        Remove a connection from the active pool.

        Args:
            connection_id: ID of the connection to remove.
        """
        self._connections.pop(connection_id, None)
        logger.info("WebSocket disconnected: %s (total active: %d)", connection_id, self.active_count)

    async def send_json(self, connection_id: str, data: dict) -> None:
        """
        Send a JSON message to a specific connection.

        Args:
            connection_id: Target connection ID.
            data: Dictionary that will be serialised to JSON.
        """
        websocket = self._connections.get(connection_id)
        if websocket is None:
            logger.warning("send_json: connection %s not found", connection_id)
            return
        try:
            await websocket.send_text(json.dumps(data))
        except Exception as exc:
            logger.error("send_json error on %s: %s", connection_id, exc)
            self.disconnect(connection_id)

    async def broadcast(self, data: dict) -> None:
        """
        Broadcast a JSON message to all active connections.

        Args:
            data: Dictionary that will be serialised and sent to every client.
        """
        if not self._connections:
            return
        payload = json.dumps(data)
        # Send to all connections concurrently
        results = await asyncio.gather(
            *[ws.send_text(payload) for ws in self._connections.values()],
            return_exceptions=True,
        )
        # Clean up any connections that failed
        failed = [
            cid
            for cid, result in zip(list(self._connections.keys()), results)
            if isinstance(result, Exception)
        ]
        for cid in failed:
            logger.warning("broadcast: removing failed connection %s", cid)
            self.disconnect(cid)


# Shared singleton used by the WebSocket router
manager = ConnectionManager()
