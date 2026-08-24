"""Run the automx ASGI service."""

from __future__ import annotations

import argparse

import uvicorn

from automx.app import create_app
from automx.commands.common import DEFAULT_CONFIG, repository


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("serve", help="run the ASGI service with Uvicorn")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    parser.add_argument("--host", default="127.0.0.1", help="listen address")
    parser.add_argument("--port", type=int, default=8000, help="listen port")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    if not 1 <= args.port <= 65_535:
        raise ValueError("--port must be between 1 and 65535")
    config_repository = repository(args.config)
    uvicorn.run(
        create_app(repository=config_repository),
        host=args.host,
        port=args.port,
        proxy_headers=False,
        server_header=False,
    )
    return 0
