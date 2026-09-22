# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe transcribe`: the transcription stage alone, no database, no API."""

from __future__ import annotations

import mimetypes
import sys
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.cli.render import format_transcript
from melliscribe.models.language import Language
from melliscribe.models.recording import PipelineStage
from melliscribe.models.transcript import Transcript
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from melliscribe.pipeline.tracing.writer import trace_call
from melliscribe.pipeline.transcription.factory import build_transcription_backend

if TYPE_CHECKING:
    import argparse

    from melliscribe.pipeline.tracing.writer import TraceSink


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register `transcribe`.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("transcribe", help="transcribe one audio file")
    parser.add_argument("audio", type=Path)
    parser.add_argument(
        "--language", required=True, choices=[x.value for x in Language]
    )
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(handler=run)


def guess_audio_format(path: Path) -> str:
    """Guess an audio file's media type from its name.

    Args:
        path: The audio file.

    Returns:
        The media type, `application/octet-stream` when unknown.
    """
    return mimetypes.guess_type(path.name)[0] or "application/octet-stream"


def transcribe_file(
    path: Path,
    language: Language,
    sink: TraceSink,
    recording_id: uuid.UUID | None = None,
) -> Transcript:
    """Transcribe one audio file with the configured backend, traced.

    Args:
        path: The audio file.
        language: The dictation language.
        sink: Where the trace row goes.
        recording_id: The recording id; random when omitted.

    Returns:
        The transcript.
    """
    backend = build_transcription_backend()
    recording_id = recording_id or uuid.uuid4()
    with trace_call(
        sink,
        recording_id=recording_id,
        stage=PipelineStage.TRANSCRIPTION,
        provider=backend.provider,
        model=backend.model,
    ):
        result = backend.transcribe(
            path.read_bytes(), guess_audio_format(path), language
        )
    return Transcript(
        id=uuid.uuid4(),
        recording_id=recording_id,
        full_text=" ".join(s.text for s in result.segments),
        segments=result.segments,
        language_detected=result.language_detected,
    )


def run(args: argparse.Namespace) -> int:
    """Transcribe and print.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    try:
        transcript = transcribe_file(
            args.audio, Language(args.language), InMemoryTraceSink()
        )
    except (RuntimeError, ValueError) as error:
        print(f"transcription failed: {error}", file=sys.stderr)
        return 1
    print(
        transcript.model_dump_json(indent=2)
        if args.json
        else format_transcript(transcript)
    )
    return 0
