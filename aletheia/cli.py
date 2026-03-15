"""
Aletheia — top-level CLI entry point.

Usage
-----
    uv run aletheia daemon              # start daemon (default host/port)
    uv run aletheia daemon --port 9000  # custom port
    uv run aletheia daemon --reload     # dev mode with auto-reload
    uv run aletheia daemon --help       # full option list

Subcommands
-----------
    daemon   Start the FastAPI daemon server
"""
import argparse
import sys


# ─── Subcommand: daemon ───────────────────────────────────────────────────────

def _add_daemon_parser(subparsers: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    p = subparsers.add_parser(
        "daemon",
        help="Start the Aletheia daemon (FastAPI + WebSocket server)",
        description=(
            "Start the Aletheia background server.\n\n"
            "The server exposes a REST API at /api/v1/* and a WebSocket\n"
            "endpoint at /ws/chat for real-time streaming chat."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--host",
        default="127.0.0.1",
        metavar="HOST",
        help="Bind address (default: 127.0.0.1)",
    )
    p.add_argument(
        "--port",
        type=int,
        default=8000,
        metavar="PORT",
        help="Listen port (default: 8000)",
    )
    p.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload on code changes (development)",
    )
    p.add_argument(
        "--workers",
        type=int,
        default=1,
        metavar="N",
        help="Number of Uvicorn worker processes (default: 1). Ignored when --reload is set.",
    )
    p.add_argument(
        "--log-level",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        metavar="LEVEL",
        help="Log level (default: info)",
    )


def _run_daemon(args: argparse.Namespace) -> None:
    from aletheia.daemon.server import start_server
    from aletheia.daemon.config import DaemonConfig

    config = DaemonConfig(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
    )

    try:
        start_server(config, reload=args.reload, workers=args.workers)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aletheia",
        description="Aletheia — intelligent document assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run aletheia daemon\n"
            "  uv run aletheia daemon --port 9000\n"
            "  uv run aletheia daemon --reload --log-level debug\n"
        ),
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    _add_daemon_parser(subparsers)

    args = parser.parse_args()

    if args.command == "daemon":
        _run_daemon(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
