# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The `melliscribe` command: one subcommand per domain library.

Arguments and stdin in, stdout out, errors to stderr, `--json` everywhere.
Exit codes follow contracts/cli.md: 0 success, 1 operation failed, 2 usage
error, 3 missing or unreadable input.
"""

from __future__ import annotations

import argparse
import sys
from typing import TYPE_CHECKING

from melliscribe.cli import dev
from melliscribe.cli import eval as eval_command
from melliscribe.cli import extract
from melliscribe.cli import openapi
from melliscribe.cli import retention
from melliscribe.cli import trace
from melliscribe.cli import transcribe
from melliscribe.cli import vocabulary
from melliscribe.cli import worker

if TYPE_CHECKING:
    from collections.abc import Sequence

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_BAD_INPUT = 3

_COMMANDS = (
    transcribe,
    extract,
    vocabulary,
    eval_command,
    retention,
    trace,
    worker,
    openapi,
    dev,
)


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with every subcommand registered.

    Returns:
        The argument parser.
    """
    parser = argparse.ArgumentParser(prog="melliscribe")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in _COMMANDS:
        command.add_parser(subparsers)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command line.

    Args:
        argv: The arguments; defaults to `sys.argv[1:]`.

    Returns:
        The process exit code.
    """
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as error:
        return EXIT_USAGE if error.code else EXIT_OK
    try:
        return args.handler(args)
    except FileNotFoundError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
