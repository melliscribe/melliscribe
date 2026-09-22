# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The processing queue: uploaded recordings, driven through the pipeline.

One pass claims every `UPLOADED` recording atomically — a recording claimed by
one pass is invisible to the next, so it is never processed twice. A single
recording is extracted live. A backlog — a beekeeper back from a dead valley
with twenty hives — is transcribed one by one and then extracted as one batch
at half cost (D4). Anything the batch did not finish by its deadline is
extracted live, and the trace says so (Principle VI).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import and_
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy import update

from melliscribe.db import repository
from melliscribe.db.tables import RecordingRow
from melliscribe.models.language import Language
from melliscribe.models.recording import PipelineStage
from melliscribe.models.recording import RecordingState
from melliscribe.pipeline.extraction.base import BatchItem
from melliscribe.pipeline.process import ensure_transcript
from melliscribe.pipeline.process import process_recording
from melliscribe.pipeline.tracing.writer import trace_call

if TYPE_CHECKING:
    from melliscribe.pipeline.extraction.base import ExtractionResult
    from melliscribe.services import Services

logger = logging.getLogger(__name__)

BATCH_THRESHOLD = 2
"""From this many waiting recordings, extraction goes through the Batch API."""


STALE_AFTER = timedelta(minutes=15)
"""A recording in flight for longer than this was left behind by a pass that
died — a crash, a restart — and is claimed again. Well above the longest
honest pass: a batch deadline plus a few minutes of transcription."""

_IN_FLIGHT = (RecordingState.TRANSCRIBING.value, RecordingState.EXTRACTING.value)


def claim_uploaded(services: Services) -> list[uuid.UUID]:
    """Claim every waiting recording for this pass, and any left stranded.

    Args:
        services: The application's services.

    Returns:
        The recordings this pass now owns, oldest capture first.
    """
    now = datetime.now(UTC)
    with services.session_factory() as session:
        candidates = session.execute(
            select(RecordingRow.id, RecordingRow.state, RecordingRow.state_changed_at)
            .where(
                or_(
                    RecordingRow.state == RecordingState.UPLOADED.value,
                    and_(
                        RecordingRow.state.in_(_IN_FLIGHT),
                        RecordingRow.state_changed_at < now - STALE_AFTER,
                    ),
                )
            )
            .order_by(RecordingRow.captured_at)
        ).all()
    claimed: list[uuid.UUID] = []
    for recording_id, state, changed_at in candidates:
        with services.session_factory.begin() as session:
            result = session.execute(
                update(RecordingRow)
                .where(RecordingRow.id == recording_id)
                .where(RecordingRow.state == state)
                .where(RecordingRow.state_changed_at == changed_at)
                .values(state=RecordingState.TRANSCRIBING.value, state_changed_at=now)
            )
            if result.rowcount == 1:
                claimed.append(recording_id)
    return claimed


def _fail_unexpectedly(
    services: Services, recording_id: uuid.UUID, error: Exception
) -> None:
    """Record an error no stage anticipated, so the recording is retryable.

    Args:
        services: The application's services.
        recording_id: The recording.
        error: What went wrong.
    """
    logger.error("processing %s failed unexpectedly", recording_id, exc_info=error)
    with services.session_factory.begin() as session:
        row = session.get_one(RecordingRow, recording_id)
        stage = (
            PipelineStage.EXTRACTION
            if row.state == RecordingState.EXTRACTING.value
            else PipelineStage.TRANSCRIPTION
        )
        row.state = RecordingState.FAILED.value
        row.failure_stage = stage.value
        row.failure_reason = str(error) or type(error).__name__


def _process_safely(
    services: Services,
    recording_id: uuid.UUID,
    precomputed: ExtractionResult | Exception | None = None,
) -> None:
    """Process one recording; an unexpected error fails it, not the pass.

    Args:
        services: The application's services.
        recording_id: The recording.
        precomputed: A batch result or error, if there is one.
    """
    try:
        process_recording(services, recording_id, precomputed=precomputed)
    except Exception as error:  # noqa: BLE001 - recorded on the recording
        _fail_unexpectedly(services, recording_id, error)


def run_queue_once(services: Services) -> int:
    """Process every waiting recording once.

    Args:
        services: The application's services.

    Returns:
        How many recordings this pass handled.
    """
    claimed = claim_uploaded(services)
    if services.batch_extractor is None or len(claimed) < BATCH_THRESHOLD:
        for recording_id in claimed:
            _process_safely(services, recording_id)
        return len(claimed)
    items: list[BatchItem] = []
    for recording_id in claimed:
        try:
            transcript = ensure_transcript(services, recording_id)
            if transcript is None:
                continue
            with services.session_factory() as session:
                row = repository.get_recording_row(session, recording_id)
                items.append(
                    BatchItem(
                        custom_id=str(recording_id),
                        transcript=transcript,
                        language=Language(row.language),
                        captured_on=row.captured_on,
                    )
                )
        except Exception as error:  # noqa: BLE001 - recorded on the recording
            _fail_unexpectedly(services, recording_id, error)
    results: dict[str, ExtractionResult | Exception] = {}
    if items:
        try:
            results = services.batch_extractor.extract_many(items)
        except Exception:
            logger.exception("batch submission failed; extracting live")
    for item in items:
        recording_id = uuid.UUID(item.custom_id)
        outcome = results.get(item.custom_id)
        if outcome is None:
            _trace_fallback(services, recording_id)
        _process_safely(services, recording_id, outcome)
    return len(claimed)


def _trace_fallback(services: Services, recording_id: uuid.UUID) -> None:
    """Record that a batch did not finish this item in time (Principle VI).

    Args:
        services: The application's services.
        recording_id: The recording falling back to live extraction.
    """
    logger.info("batch deadline passed for %s; extracting live", recording_id)
    with trace_call(
        services.trace_sink,
        recording_id=recording_id,
        stage=PipelineStage.EXTRACTION,
        provider="anthropic-batch",
        model="none",
    ) as call:
        call.fallback_taken = True
