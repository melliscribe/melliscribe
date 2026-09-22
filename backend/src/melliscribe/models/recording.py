# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The captured audio: the shortest-lived entity in the system (FR-027c)."""

from __future__ import annotations

from datetime import date
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from melliscribe.models.base import Model
from melliscribe.models.language import Language


class RecordingState(StrEnum):
    """Where a recording is in the pipeline (data-model.md transitions)."""

    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"
    TRANSCRIBING = "transcribing"
    EXTRACTING = "extracting"
    PROCESSED = "processed"
    NO_INSPECTION = "no_inspection"
    """Intelligible, but no inspection content: no record (FR-016b)."""
    FAILED = "failed"


class PipelineStage(StrEnum):
    """A pipeline stage, used to attribute failures (FR-019b) and traces."""

    TRANSCRIPTION = "transcription"
    EXTRACTION = "extraction"


class Recording(Model):
    """A captured recording and its processing state.

    Attributes:
        id: Client-generated at capture time; the upload idempotency key and
            the batch `custom_id` (FR-020).
        captured_at: When it was captured, on the device.
        captured_on: The device's local calendar day at capture.
        duration_seconds: Its length.
        language: Copied from the account setting at capture (FR-026).
        audio_format: The detected media type, never assumed (D9).
        state: Where it is in the pipeline.
        retention_expires_at: When the audio will be deleted; None once gone.
        audio_available: False after deletion or expiry (FR-027d).
        failure_reason: Why processing failed; never swallowed (FR-019).
        failure_stage: Which stage failed (FR-019b).
        reprocess_failed: True when the last re-processing did not take and
            the previous record was kept (FR-019c).
        eval_consent_at: When the beekeeper explicitly consented to this
            recording being used for evaluation; None means no (FR-027f).
    """

    id: UUID
    captured_at: datetime
    captured_on: date
    duration_seconds: float
    language: Language
    audio_format: str
    state: RecordingState
    retention_expires_at: datetime | None = None
    audio_available: bool = True
    failure_reason: str | None = None
    failure_stage: PipelineStage | None = None
    reprocess_failed: bool = False
    eval_consent_at: datetime | None = None
