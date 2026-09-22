# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Drive a recording through transcription and extraction.

The rules this module exists to keep:

- **The recording is never lost.** A failure moves it to `FAILED` with the
  stage that failed (FR-019, FR-019b); the audio stays.
- **Work that succeeded is kept.** A transcript survives an extraction failure
  and is reused on retry rather than transcribed again (FR-019a).
- **Re-processing is all or nothing.** After a language correction, the new
  transcript and record are written together only if both stages succeed;
  otherwise the previous record stays exactly as it was and the recording says
  the re-processing did not take (FR-019c). Confirmed fields are carried over
  by [assemble_record][melliscribe.domain.inspection.assemble.assemble_record]
  (FR-010, FR-026c).
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

from melliscribe.db import repository
from melliscribe.db.tables import RecordingRow
from melliscribe.domain.inspection.assemble import AssemblyContext
from melliscribe.domain.inspection.assemble import assemble_record
from melliscribe.models.language import Language
from melliscribe.models.recording import PipelineStage
from melliscribe.models.recording import RecordingState
from melliscribe.models.transcript import Transcript
from melliscribe.pipeline.tracing.writer import trace_call

if TYPE_CHECKING:
    from datetime import date

    from melliscribe.models.hive import Hive
    from melliscribe.models.inspection import InspectionRecord
    from melliscribe.pipeline.extraction.base import ExtractionResult
    from melliscribe.services import Services

logger = logging.getLogger(__name__)


class StageFailedError(Exception):
    """A pipeline stage failed; carries the stage for attribution."""

    def __init__(self, stage: PipelineStage, reason: str) -> None:
        super().__init__(reason)
        self.stage = stage
        self.reason = reason


def _set_state(
    services: Services, recording_id: uuid.UUID, state: RecordingState
) -> None:
    """Record a state transition in its own transaction, so it is visible.

    Args:
        services: The application's services.
        recording_id: The recording.
        state: The new state.
    """
    with services.session_factory.begin() as session:
        session.get_one(RecordingRow, recording_id).state = state.value


def _transcribe(
    services: Services, recording_id: uuid.UUID, audio_format: str, language: Language
) -> Transcript:
    """Run the transcription stage, traced.

    Args:
        services: The application's services.
        recording_id: The recording.
        audio_format: Its media type.
        language: The language to transcribe in.

    Returns:
        The transcript, not yet saved.

    Raises:
        StageFailedError: When transcription fails.
    """
    backend = services.transcriber
    try:
        audio = services.audio_store.read(recording_id)
        with trace_call(
            services.trace_sink,
            recording_id=recording_id,
            stage=PipelineStage.TRANSCRIPTION,
            provider=backend.provider,
            model=backend.model,
        ):
            result = backend.transcribe(audio, audio_format, language)
        if not result.segments:
            msg = "the transcription contains no segments"
            raise ValueError(msg)  # noqa: TRY301 - attributed below like any failure
    except Exception as error:
        raise StageFailedError(PipelineStage.TRANSCRIPTION, str(error)) from error
    return Transcript(
        id=uuid.uuid4(),
        recording_id=recording_id,
        full_text=" ".join(s.text for s in result.segments),
        segments=result.segments,
        language_detected=result.language_detected,
    )


@dataclass(frozen=True)
class _Snapshot:
    """What processing reads from the database before calling any stage."""

    language: Language
    audio_format: str
    captured_on: date
    state: RecordingState
    transcript: Transcript | None
    asr: tuple[str, str] | None
    record: InspectionRecord | None
    hives: list[Hive]


def _load(services: Services, recording_id: uuid.UUID) -> _Snapshot:
    """Read everything processing needs, in one short transaction.

    Args:
        services: The application's services.
        recording_id: The recording.

    Returns:
        The snapshot.
    """
    with services.session_factory.begin() as session:
        row = repository.get_recording_row(session, recording_id)
        transcript = repository.get_transcript(session, recording_id)
        existing = repository.get_record_for_recording(session, recording_id)
        return _Snapshot(
            language=Language(row.language),
            audio_format=row.audio_format,
            captured_on=row.captured_on,
            state=RecordingState(row.state),
            transcript=transcript,
            asr=repository.get_transcript_provenance(session, recording_id)
            if transcript is not None
            else None,
            record=existing[0] if existing else None,
            hives=repository.list_hives(session),
        )


def ensure_transcript(services: Services, recording_id: uuid.UUID) -> Transcript | None:
    """Make sure a recording has a saved transcript, recording any failure.

    Used by the batch path, which transcribes each recording before batching
    their extractions.

    Args:
        services: The application's services.
        recording_id: The recording.

    Returns:
        The transcript, or None when transcription failed (recorded as such).
    """
    snapshot = _load(services, recording_id)
    try:
        transcript, _, _ = _obtain_transcript(
            services, recording_id, snapshot, snapshot.language, persist=True
        )
    except StageFailedError as failure:
        _record_failure(services, recording_id, snapshot, failure, reprocess=False)
        return None
    return transcript


def _obtain_transcript(
    services: Services,
    recording_id: uuid.UUID,
    snapshot: _Snapshot,
    language: Language,
    *,
    persist: bool,
) -> tuple[Transcript, str, str]:
    """Reuse the transcript, or transcribe when there is none or the language changed.

    Args:
        services: The application's services.
        recording_id: The recording.
        snapshot: The recording as loaded.
        language: The language to transcribe in.
        persist: Save a fresh transcript at once, so it survives an extraction
            failure (FR-019a). False when re-processing, which is all or nothing.

    Returns:
        The transcript, keeping any existing transcript id, and the ASR
        provider and model that produced it.
    """
    if (
        snapshot.transcript is not None
        and snapshot.asr is not None
        and language == snapshot.language
    ):
        return snapshot.transcript, *snapshot.asr
    transcript = _transcribe(services, recording_id, snapshot.audio_format, language)
    if snapshot.transcript is not None:
        transcript = transcript.model_copy(update={"id": snapshot.transcript.id})
    provider, model = services.transcriber.provider, services.transcriber.model
    if persist:
        with services.session_factory.begin() as session:
            repository.save_transcript(session, transcript, provider, model)
    return transcript, provider, model


def _record_failure(
    services: Services,
    recording_id: uuid.UUID,
    snapshot: _Snapshot,
    failure: StageFailedError,
    *,
    reprocess: bool,
) -> None:
    """Record a failure, keeping the recording and any previous record.

    Args:
        services: The application's services.
        recording_id: The recording.
        snapshot: The recording as loaded.
        failure: The failure and its stage.
        reprocess: Whether this was a re-processing of an existing record.
    """
    logger.warning("recording %s failed at %s", recording_id, failure.stage)
    with services.session_factory.begin() as session:
        row = session.get_one(RecordingRow, recording_id)
        if reprocess and snapshot.record is not None:
            row.reprocess_failed = True
            row.state = snapshot.state.value
        else:
            row.state = RecordingState.FAILED.value
        row.failure_stage = failure.stage.value
        row.failure_reason = failure.reason


def _extract(
    services: Services,
    transcript: Transcript,
    language: Language,
    snapshot: _Snapshot,
    precomputed: ExtractionResult | Exception | None,
) -> ExtractionResult:
    """Run the extraction stage, or take a result already obtained.

    Args:
        services: The application's services.
        transcript: The transcript.
        language: The language to extract against.
        snapshot: The recording as loaded.
        precomputed: A batch result or error, if there is one.

    Returns:
        The extraction.

    Raises:
        StageFailedError: When extraction failed.
    """
    if isinstance(precomputed, Exception):
        raise StageFailedError(PipelineStage.EXTRACTION, str(precomputed))
    if precomputed is not None:
        return precomputed
    try:
        return services.extractor.extract(transcript, language, snapshot.captured_on)
    except Exception as error:
        raise StageFailedError(PipelineStage.EXTRACTION, str(error)) from error


def process_recording(
    services: Services,
    recording_id: uuid.UUID,
    *,
    language: Language | None = None,
    reprocess: bool = False,
    precomputed: ExtractionResult | Exception | None = None,
) -> None:
    """Process, retry or re-process one recording.

    Args:
        services: The application's services.
        recording_id: The recording.
        language: A corrected language; forces a fresh transcription.
        reprocess: Whether a record may already exist and must be preserved
            on failure.
        precomputed: An extraction already obtained elsewhere — from a batch —
            or its error. None extracts live.
    """
    snapshot = _load(services, recording_id)
    target = language or snapshot.language
    if not reprocess:
        _set_state(services, recording_id, RecordingState.TRANSCRIBING)
    try:
        transcript, provider, model = _obtain_transcript(
            services, recording_id, snapshot, target, persist=not reprocess
        )
        if not reprocess:
            _set_state(services, recording_id, RecordingState.EXTRACTING)
        result = _extract(services, transcript, target, snapshot, precomputed)
    except StageFailedError as failure:
        _record_failure(services, recording_id, snapshot, failure, reprocess=reprocess)
        return
    record = assemble_record(
        result,
        transcript,
        AssemblyContext(
            recording_id=recording_id,
            language=target,
            captured_on=snapshot.captured_on,
            hives=snapshot.hives,
            transcription_provider=provider,
            transcription_model=model,
            previous=snapshot.record,
        ),
    )
    with services.session_factory.begin() as session:
        row = session.get_one(RecordingRow, recording_id)
        if record is None and snapshot.record is not None:
            row.reprocess_failed = True
            row.state = snapshot.state.value
            return
        repository.save_transcript(session, transcript, provider, model)
        row.language = target.value
        row.failure_stage = None
        row.failure_reason = None
        row.reprocess_failed = False
        if record is None:
            row.state = RecordingState.NO_INSPECTION.value
            return
        repository.save_record(session, record)
        row.state = RecordingState.PROCESSED.value
