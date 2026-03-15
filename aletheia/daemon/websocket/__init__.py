"""
WebSocket support for Aletheia Daemon - Phase 2

Provides real-time bidirectional communication for chat.
"""

from .manager import ConnectionManager
from .chat import router

__all__ = ['ConnectionManager', 'router']
