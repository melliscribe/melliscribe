# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe vocabulary`: list the vocabularies and gate their labels."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.vocabulary.check import DEFAULT_CATALOGUE_DIR
from melliscribe.domain.vocabulary.check import find_vocabulary_gaps
from melliscribe.models.vocabulary import VOCABULARIES
from melliscribe.models.vocabulary import VOCABULARY_VERSION

if TYPE_CHECKING:
    import argparse


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register the `vocabulary` subcommands.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("vocabulary", help="controlled vocabularies")
    commands = parser.add_subparsers(dest="vocabulary_command", required=True)

    list_parser = commands.add_parser("list", help="list every vocabulary")
    list_parser.add_argument("--language", choices=["fr", "en"])
    list_parser.add_argument(
        "--catalogue-dir", type=Path, default=DEFAULT_CATALOGUE_DIR
    )
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(handler=list_vocabularies)

    check_parser = commands.add_parser("check", help="fail on any missing label")
    check_parser.add_argument(
        "--catalogue-dir", type=Path, default=DEFAULT_CATALOGUE_DIR
    )
    check_parser.add_argument("--json", action="store_true")
    check_parser.set_defaults(handler=check_vocabularies)


def list_vocabularies(args: argparse.Namespace) -> int:
    """Print every vocabulary with its definitions and, optionally, labels.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    labels: dict[str, Any] = {}
    if args.language:
        catalogue = json.loads(
            (args.catalogue_dir / f"{args.language}.json").read_text("utf-8")
        )
        labels = catalogue["vocabulary"]
    listing: dict[str, Any] = {
        "version": VOCABULARY_VERSION,
        "vocabularies": {
            name: {
                "ordered": vocabulary.ordered,
                "membership": vocabulary.membership,
                "values": [
                    {
                        "id": value.value,
                        "definition": vocabulary.definitions[value.value],
                        "superseded": value.value in vocabulary.superseded,
                        "label": labels.get(name, {}).get(value.value),
                    }
                    for value in vocabulary.values
                ],
            }
            for name, vocabulary in VOCABULARIES.items()
        },
    }
    if args.json:
        print(json.dumps(listing, ensure_ascii=False, indent=2))
        return 0
    print(f"vocabulary version {VOCABULARY_VERSION}")
    for name, vocabulary in VOCABULARIES.items():
        print(f"\n{name} ({'ordered' if vocabulary.ordered else 'unordered'})")
        for value in vocabulary.values:
            label = labels.get(name, {}).get(value.value)
            suffix = f" — {label}" if label else ""
            print(f"  {value.value}{suffix}: {vocabulary.definitions[value.value]}")
    return 0


def check_vocabularies(args: argparse.Namespace) -> int:
    """Exit non-zero when any label, definition or glossary form is missing.

    Args:
        args: The parsed arguments.

    Returns:
        0 when complete, 1 on any gap.
    """
    gaps = find_vocabulary_gaps(args.catalogue_dir)
    if args.json:
        print(json.dumps({"gaps": gaps}, ensure_ascii=False))
    for gap in gaps:
        print(gap, file=sys.stderr)
    if not gaps and not args.json:
        print("vocabularies and catalogues complete")
    return 1 if gaps else 0
