"""
Aletheia Daemon

A FastAPI-based service for running Aletheia as a background daemon.
"""

from .server import start_server, stop_server
from .config import DaemonConfig
from .main import create_app

__all__ = ['start_server', 'stop_server', 'DaemonConfig', 'create_app']
