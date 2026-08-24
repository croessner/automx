"""Export and validate the generated OpenAPI 3.1 contract."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fastapi.openapi.models import OpenAPI

from automx.app import create_app
from automx.commands.common import DEFAULT_CONFIG


def register(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    parser = subparsers.add_parser("openapi", help="inspect the OpenAPI contract")
    commands = parser.add_subparsers(dest="openapi_command", required=True)
    export = commands.add_parser("export", help="export deterministic OpenAPI 3.1 JSON")
    export.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    export.add_argument("--output", default="-", help="output path, or - for stdout")
    export.set_defaults(handler=run_export)
    check = commands.add_parser("check", help="validate the generated OpenAPI model")
    check.add_argument("--config", default=DEFAULT_CONFIG, help="path to automx.conf")
    check.set_defaults(handler=run_check)


def schema(config_path: str) -> dict[str, Any]:
    result: dict[str, Any] = create_app(config_path=config_path).openapi()
    OpenAPI.model_validate(result)
    return result


def serialized_schema(config_path: str) -> str:
    return json.dumps(schema(config_path), indent=2, sort_keys=True) + "\n"


def run_export(args: argparse.Namespace) -> int:
    document = serialized_schema(args.config)
    if args.output == "-":
        sys.stdout.write(document)
    else:
        Path(args.output).write_text(document, encoding="utf-8")
    return 0


def run_check(args: argparse.Namespace) -> int:
    document = schema(args.config)
    print(f"OpenAPI {document['openapi']} document valid ({len(document['paths'])} paths).")
    return 0
