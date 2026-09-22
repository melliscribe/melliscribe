# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe openapi`: write the OpenAPI schema the frontend types come from."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register `openapi`.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("openapi", help="write the OpenAPI schema")
    parser.add_argument("--output", type=Path, help="default: stdout")
    parser.set_defaults(handler=run)


def build_schema() -> dict[str, Any]:
    """Generate the OpenAPI schema from the application.

    Returns:
        The schema. Building it needs no database and no credentials.
    """
    from fastapi.openapi.utils import get_openapi  # noqa: PLC0415

    from melliscribe.api import hives  # noqa: PLC0415
    from melliscribe.api import recordings  # noqa: PLC0415
    from melliscribe.api import records  # noqa: PLC0415
    from melliscribe.api import settings  # noqa: PLC0415
    from melliscribe.api.app import API_VERSION  # noqa: PLC0415

    routes = [
        route
        for module in (settings, hives, recordings, records)
        for route in module.router.routes
    ]
    return get_openapi(title="Melliscribe", version=API_VERSION, routes=routes)


def run(args: argparse.Namespace) -> int:
    """Print or write the schema, with sorted keys so diffs are stable.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    text = (
        json.dumps(build_schema(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    )
    if args.output:
        args.output.write_text(text, "utf-8")
    else:
        sys.stdout.write(text)
    return 0
