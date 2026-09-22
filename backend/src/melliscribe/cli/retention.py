# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe retention`: what is about to expire, and expiring it."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.api.app import build_services
from melliscribe.domain.retention.expiry import apply_expiry
from melliscribe.domain.retention.expiry import find_due

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register the `retention` subcommands.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("retention", help="audio retention")
    commands = parser.add_subparsers(dest="retention_command", required=True)
    due = commands.add_parser("due", help="recordings approaching or past expiry")
    due.add_argument("--within-days", type=int, default=30)
    due.add_argument("--json", action="store_true")
    due.set_defaults(handler=run_due)
    apply = commands.add_parser("apply", help="delete expired audio")
    apply.add_argument("--dry-run", action="store_true")
    apply.add_argument("--json", action="store_true")
    apply.set_defaults(handler=run_apply)


def run_due(args: argparse.Namespace) -> int:
    """List what expires soon, marking what needs attention.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    services = build_services()
    with services.session_factory() as session:
        due = find_due(session, now=datetime.now(UTC), within_days=args.within_days)
    if args.json:
        print(json.dumps([asdict(d) for d in due], default=str))
        return 0
    for item in due:
        flag = "  NEEDS ATTENTION" if item.needs_attention else ""
        print(f"{item.recording_id} expires {item.expires_at:%Y-%m-%d}{flag}")
    return 0


def run_apply(args: argparse.Namespace) -> int:
    """Delete expired audio; `--dry-run` only reports.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    services = build_services()
    with services.session_factory.begin() as session:
        removed = apply_expiry(
            session, services.audio_store, now=datetime.now(UTC), dry_run=args.dry_run
        )
    if args.json:
        print(json.dumps({"dry_run": args.dry_run, "recordings": removed}))
    else:
        verb = "would delete" if args.dry_run else "deleted"
        print(f"{verb} {len(removed)} audio file(s)")
    return 0
