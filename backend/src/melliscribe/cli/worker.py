# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe worker`: drain the processing queue, and keep draining it.

Uploads start a pass themselves; the worker is what catches anything left
behind by a restart, and what turns a backlog into one batch.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.api.app import build_services
from melliscribe.pipeline.queue import run_queue_once

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register `worker`.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("worker", help="process queued recordings")
    parser.add_argument("--once", action="store_true", help="one pass, then exit")
    parser.add_argument("--interval", type=float, default=30.0, help="seconds")
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    """Run queue passes until interrupted.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    services = build_services()
    while True:
        handled = run_queue_once(services)
        if handled:
            print(f"processed {handled} recording(s)")
        if args.once:
            return 0
        time.sleep(args.interval)
