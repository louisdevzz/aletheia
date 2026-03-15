"""
Server Management

Start and stop the Aletheia Daemon server.
"""
import uvicorn
from typing import Optional
import signal
import sys

from .config import DaemonConfig


_server_process = None


def start_server(
    config: Optional[DaemonConfig] = None,
    reload: bool = False,
    workers: int = 1
) -> None:
    """
    Start the Aletheia Daemon server.
    
    Args:
        config: Server configuration
        reload: Enable auto-reload (development)
        workers: Number of worker processes
    """
    if config is None:
        config = DaemonConfig.from_env()
    
    print(f"""
╔══════════════════════════════════════════════════╗
║            Aletheia Daemon                    ║
╠══════════════════════════════════════════════════╣
║  Host:   {config.host:<35} ║
║  Port:   {config.port:<35} ║
║  Log:    {config.log_level:<35} ║
╚══════════════════════════════════════════════════╝
    """)
    
    # When reload is enabled, use import string; otherwise use app instance
    if reload:
        # Use import string for reload mode
        app_str = "aletheia.daemon.main:create_app"
        uvicorn.run(
            app_str,
            host=config.host,
            port=config.port,
            log_level=config.log_level,
            reload=True,
            workers=1,
            factory=True  # create_app is a factory function
        )
    else:
        # Use app instance directly for production
        from .main import create_app
        app = create_app(config)
        uvicorn.run(
            app,
            host=config.host,
            port=config.port,
            log_level=config.log_level,
            reload=False,
            workers=workers
        )


def stop_server() -> None:
    """
    Stop the running server.
    
    Note: This is primarily for programmatic use.
    When running from CLI, use Ctrl+C.
    """
    print("\n🛑 Stopping Aletheia Daemon...")
    # uvicorn handles SIGINT/SIGTERM gracefully
    signal.raise_signal(signal.SIGINT)


def main():
    """CLI entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Aletheia Daemon")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=8000, help="Server port")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--workers", type=int, default=1, help="Number of workers")
    parser.add_argument("--log-level", default="info", help="Log level")
    
    args = parser.parse_args()
    
    config = DaemonConfig(
        host=args.host,
        port=args.port,
        log_level=args.log_level
    )
    
    try:
        start_server(config, reload=args.reload, workers=args.workers)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


if __name__ == "__main__":
    main()
