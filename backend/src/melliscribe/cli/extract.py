# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe extract` and `melliscribe pipeline`: the replay commands.

A beekeeper reports a wrong record: pull the transcript (or the recording) and
re-run the exact stage against it, with no API, no PWA and no browser.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC
from datetime import date
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.cli.render import format_record
from melliscribe.cli.transcribe import transcribe_file
from melliscribe.domain.inspection.assemble import AssemblyContext
from melliscribe.domain.inspection.assemble import assemble_record
from melliscribe.models.hive import Hive
from melliscribe.models.language import Language
from melliscribe.models.transcript import Transcript
from melliscribe.models.transcript import TranscriptSegment
from melliscribe.pipeline.extraction.claude import ClaudeExtractor
from melliscribe.pipeline.extraction.prompts import CURRENT_PROMPT_VERSION
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink

if TYPE_CHECKING:
    import argparse

_HIVE_NAMESPACE = uuid.UUID("5d1f0c8e-2a47-4b8e-8d0f-3c6b9e1a7f24")


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register `extract` and `pipeline`.

    Args:
        subparsers: The top-level subparsers action.
    """
    extract = subparsers.add_parser("extract", help="extract one transcript")
    extract.add_argument("transcript", help="transcript JSON or text file, or -")
    _add_common(extract)
    extract.add_argument("--prompt-version", default=CURRENT_PROMPT_VERSION)
    extract.add_argument("--no-cache", action="store_true")
    extract.set_defaults(handler=run_extract)

    pipeline = subparsers.add_parser("pipeline", help="transcribe and extract audio")
    pipeline.add_argument("audio", type=Path)
    _add_common(pipeline)
    pipeline.set_defaults(handler=run_pipeline, prompt_version=CURRENT_PROMPT_VERSION)
    pipeline.set_defaults(no_cache=False)


def _add_common(parser: argparse.ArgumentParser) -> None:
    """Add the options both commands share.

    Args:
        parser: The subcommand parser.
    """
    parser.add_argument(
        "--language", required=True, choices=[x.value for x in Language]
    )
    parser.add_argument(
        "--captured-on", type=date.fromisoformat, default=None, help="default: today"
    )
    parser.add_argument(
        "--hive", action="append", default=[], help="a known hive identifier"
    )
    parser.add_argument("--json", action="store_true")


def read_transcript(source: str) -> Transcript:
    """Read a transcript from a file or stdin.

    JSON is a [Transcript][melliscribe.models.transcript.Transcript] or an
    object with `segments`; anything else is plain text, one segment per line.

    Args:
        source: A path, or `-` for stdin.

    Returns:
        The transcript.
    """
    text = sys.stdin.read() if source == "-" else Path(source).read_text("utf-8")
    recording_id = uuid.uuid4()
    data: dict[str, Any]
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        data = {
            "segments": [
                {"text": line, "start_seconds": 0.0, "end_seconds": 0.0}
                for line in lines
            ]
        }
    segments = [TranscriptSegment.model_validate(s) for s in data["segments"]]
    return Transcript(
        id=uuid.uuid4(),
        recording_id=uuid.UUID(data.get("recording_id", str(recording_id))),
        full_text=" ".join(s.text for s in segments),
        segments=segments,
        language_detected=data.get("language_detected"),
    )


def extract_and_print(
    transcript: Transcript, args: argparse.Namespace, sink: InMemoryTraceSink
) -> int:
    """Extract a transcript, assemble the record and print it.

    Args:
        transcript: The transcript.
        args: The parsed arguments.
        sink: Where trace rows go; summarised on stderr.

    Returns:
        The exit code.
    """
    language = Language(args.language)
    captured_on = args.captured_on or datetime.now(UTC).date()
    extractor = ClaudeExtractor(
        sink, prompt_version=args.prompt_version, use_cache=not args.no_cache
    )
    try:
        result = extractor.extract(transcript, language, captured_on)
    except Exception as error:  # noqa: BLE001 - reported, with its trace
        print(f"extraction failed: {error}", file=sys.stderr)
        return 1
    finally:
        for trace in sink.traces:
            print(
                f"trace: {trace.stage.value} {trace.model} {trace.outcome.value} "
                f"{trace.latency_ms}ms ${trace.cost_usd:.4f} "
                f"cache_read={trace.cache_read_tokens}",
                file=sys.stderr,
            )
    hives = [
        Hive(
            id=uuid.uuid5(_HIVE_NAMESPACE, identifier),
            identifier=identifier,
            created_at=datetime.now(UTC),
        )
        for identifier in args.hive
    ]
    record = assemble_record(
        result,
        transcript,
        AssemblyContext(
            recording_id=transcript.recording_id,
            language=language,
            captured_on=captured_on,
            hives=hives,
            transcription_provider="cli",
            transcription_model="cli",
        ),
    )
    if record is None:
        print(
            json.dumps({"record": None, "reason": "no_inspection"})
            if args.json
            else "no inspection recognised (FR-016b)"
        )
        return 0
    print(record.model_dump_json(indent=2) if args.json else format_record(record))
    return 0


def run_extract(args: argparse.Namespace) -> int:
    """Run `extract`.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    return extract_and_print(
        read_transcript(args.transcript), args, InMemoryTraceSink()
    )


def run_pipeline(args: argparse.Namespace) -> int:
    """Run `pipeline`: both stages, the same path the API takes.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    sink = InMemoryTraceSink()
    try:
        transcript = transcribe_file(args.audio, Language(args.language), sink)
    except (RuntimeError, ValueError) as error:
        print(f"transcription failed: {error}", file=sys.stderr)
        return 1
    return extract_and_print(transcript, args, sink)
