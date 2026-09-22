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
from typing import TYPE_CHECKING

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
    from melliscribe.services import Services

logger = logging.getLogger(__name__)

BATCH_THRESHOLD = 2
"""From this many waiting recordings, extraction goes through the Batch API."""


def claim_uploaded(services: Services) -> list[uuid.UUID]:
    """Claim every uploaded recording for this pass.

    Args:
        services: The application's services.

    Returns:
        The recordings this pass now owns, oldest capture first.
    """
    with services.session_factory() as session:
        candidates = list(
            session.scalars(
                select(RecordingRow.id)
                .where(RecordingRow.state == RecordingState.UPLOADED.value)
                .order_by(RecordingRow.captured_at)
            )
        )
    claimed: list[uuid.UUID] = []
    for recording_id in candidates:
        with services.session_factory.begin() as session:
            result = session.execute(
                update(RecordingRow)
                .where(RecordingRow.id == recording_id)
                .where(RecordingRow.state == RecordingState.UPLOADED.value)
                .values(state=RecordingState.TRANSCRIBING.value)
            )
            if result.rowcount == 1:
                claimed.append(recording_id)
    return claimed


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
            process_recording(services, recording_id)
        return len(claimed)
    items: list[BatchItem] = []
    for recording_id in claimed:
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
    results = services.batch_extractor.extract_many(items) if items else {}
    for item in items:
        recording_id = uuid.UUID(item.custom_id)
        outcome = results.get(item.custom_id)
        if outcome is None:
            _trace_fallback(services, recording_id)
        process_recording(services, recording_id, precomputed=outcome)
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
