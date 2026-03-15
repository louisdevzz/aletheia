"""
System API Routes

Health checks and system status
"""

from fastapi import APIRouter
from pydantic import BaseModel
from datetime import datetime

from aletheia.config.settings import storage_config
from aletheia.rag.storage import get_storage

router = APIRouter(tags=["system"])


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    version: str = "0.1.0"


class StatusResponse(BaseModel):
    status: str
    storage: dict
    timestamp: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint.

    Returns 200 OK if service is running.
    """
    return HealthResponse(status="healthy", timestamp=datetime.now().isoformat())


@router.get("/status", response_model=StatusResponse)
async def system_status():
    """
    Get detailed system status.

    Returns storage statistics and service status.
    """
    try:
        storage = get_storage()
        stats = storage.get_stats()
        storage_status = "connected"
    except Exception as e:
        stats = {}
        storage_status = f"error: {str(e)}"

    return StatusResponse(
        status="running",
        storage={
            "type": "sqlite",
            "path": storage_config.db_path,
            "status": storage_status,
            "stats": stats,
        },
        timestamp=datetime.now().isoformat(),
    )
