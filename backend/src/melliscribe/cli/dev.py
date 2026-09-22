# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe dev`: development helpers. Not for production data.

`seed` turns a typed transcript into a stored recording and record — through
the real extraction stage — so the review screen can be exercised without
dictating. The seeded recording has no audio, and the review screen says so.
"""

from __future__ import annotations

import sys
import uuid
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.api.app import build_services
from melliscribe.db import repository
from melliscribe.db.tables import RecordingRow
from melliscribe.models.language import Language
from melliscribe.models.recording import RecordingState
from melliscribe.models.transcript import Transcript
from melliscribe.models.transcript import TranscriptSegment
from melliscribe.pipeline.process import process_recording

if TYPE_CHECKING:
    import argparse

    from melliscribe.services import Services


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register the `dev` subcommands.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("dev", help="development helpers")
    commands = parser.add_subparsers(dest="dev_command", required=True)
    seed = commands.add_parser("seed", help="store a record from a typed transcript")
    seed.add_argument("transcript", type=Path, help="text file, one segment per line")
    seed.add_argument("--language", required=True, choices=[x.value for x in Language])
    seed.add_argument("--hive", action="append", default=[], help="create this hive")
    seed.set_defaults(handler=run_seed)


def seed_transcript(
    services: Services, lines: list[str], language: Language, hives: list[str]
) -> uuid.UUID:
    """Store a recording from typed lines and run extraction on it.

    Args:
        services: The application's services.
        lines: The transcript, one segment per line.
        language: The dictation language.
        hives: Hive identifiers to create first, when missing.

    Returns:
        The seeded recording's id.
    """
    now = datetime.now(UTC)
    recording_id = uuid.uuid4()
    segments = [
        TranscriptSegment(text=line, start_seconds=5.0 * i, end_seconds=5.0 * i + 4.5)
        for i, line in enumerate(lines)
    ]
    with services.session_factory.begin() as session:
        existing = {h.identifier for h in repository.list_hives(session)}
        for identifier in hives:
            if identifier not in existing:
                repository.create_hive(session, identifier)
        session.add(
            RecordingRow(
                id=recording_id,
                captured_at=now,
                captured_on=now.date(),
                duration_seconds=5.0 * len(lines),
                language=language.value,
                audio_format="text/plain",
                state=RecordingState.UPLOADED.value,
                retention_expires_at=None,
                audio_available=False,
                audio_key=None,
                reprocess_failed=False,
                created_at=now,
            )
        )
        session.flush()
        repository.save_transcript(
            session,
            Transcript(
                id=uuid.uuid4(),
                recording_id=recording_id,
                full_text=" ".join(lines),
                segments=segments,
            ),
            provider="dev-seed",
            model="typed",
        )
    process_recording(services, recording_id)
    return recording_id


def run_seed(args: argparse.Namespace) -> int:
    """Seed one record and report its state.

    Args:
        args: The parsed arguments.

    Returns:
        0 when a record was produced, 1 otherwise.
    """
    lines = [
        line.strip()
        for line in args.transcript.read_text("utf-8").splitlines()
        if line.strip()
    ]
    services = build_services()
    recording_id = seed_transcript(services, lines, Language(args.language), args.hive)
    with services.session_factory() as session:
        row = repository.get_recording_row(session, recording_id)
        print(f"recording {recording_id}: {row.state}")
        if row.failure_reason:
            print(f"  {row.failure_stage}: {row.failure_reason}", file=sys.stderr)
    return 0 if row.state == RecordingState.PROCESSED.value else 1
