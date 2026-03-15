"""
FastAPI Application for Aletheia Daemon
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import DaemonConfig
from .api import documents, chat, system
from .websocket import router as ws_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s][%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def _initialize_workspace():
    """Initialize workspace with identity files from templates and memory directory."""
    from aletheia.config.settings import get_workspace_dir
    from pathlib import Path
    import datetime

    workspace = get_workspace_dir()

    # Create workspace directory
    workspace_dir = workspace / "workspace"
    workspace_dir.mkdir(exist_ok=True)

    # Create memory directory for SQLite database
    memory_dir = workspace / "memory"
    memory_dir.mkdir(exist_ok=True)
    print(f"  ✓ Memory directory: {memory_dir}")

    # Template files are in the aletheia package directory
    aletheia_package_dir = Path(__file__).parent.parent
    template_files = {
        "AGENTS.md": aletheia_package_dir / "AGENTS.md",
        "SOUL.md": aletheia_package_dir / "SOUL.md",
        "TOOLS.md": aletheia_package_dir / "TOOLS.md",
        "IDENTITY.md": aletheia_package_dir / "IDENTITY.md",
        "USER.md": aletheia_package_dir / "USER.md",
        "BOOTSTRAP.md": aletheia_package_dir / "BOOTSTRAP.md",
    }

    created_count = 0
    for filename, template_path in template_files.items():
        target_path = workspace_dir / filename
        if not target_path.exists():
            if template_path.exists():
                # Read template and copy to workspace
                content = template_path.read_text()

                # Replace template variables
                content = content.replace(
                    "First interaction:",
                    f"First interaction: {datetime.datetime.now().isoformat()}",
                )

                target_path.write_text(content)
                created_count += 1
                print(f"  ✓ Created {filename}")
            else:
                print(f"  ⚠ Template not found: {template_path}")

    if created_count > 0:
        print(f"  ✓ Created {created_count} identity files in {workspace_dir}")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Manage application lifespan."""
    # Startup
    print("🚀 Starting Aletheia Daemon...")
    _initialize_workspace()
    yield
    # Shutdown
    print("🛑 Shutting down Aletheia Daemon...")


def create_app(config: DaemonConfig = None) -> FastAPI:
    """
    Create and configure FastAPI application.

    Args:
        config: Daemon configuration

    Returns:
        Configured FastAPI app
    """
    if config is None:
        config = DaemonConfig.from_env()

    app = FastAPI(
        title="Aletheia API",
        description="API for Aletheia - Intelligent document assistant",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=config.cors_allow_credentials,
        allow_methods=config.cors_allow_methods,
        allow_headers=config.cors_allow_headers,
    )

    # Include routers
    app.include_router(documents.router, prefix="/api/v1")
    app.include_router(chat.router, prefix="/api/v1")
    app.include_router(system.router, prefix="/api/v1")

    # WebSocket router (Phase 2) - no prefix so endpoint is exactly WS /ws/chat
    app.include_router(ws_router)

    return app
