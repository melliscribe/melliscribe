# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One row per LLM or ASR call (Principle VI, ADR-0006)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from melliscribe.models.base import Model
from melliscribe.models.recording import PipelineStage


class TraceOutcome(StrEnum):
    """How a call ended. Errors are recorded, never swallowed."""

    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"


class LLMTrace(Model):
    """A traced pipeline call.

    Attributes:
        id: Trace identifier.
        recording_id: The recording the call was made for.
        stage: Transcription or extraction.
        provider: Who served the call.
        model: The model that served the call.
        prompt_version: The prompt version, when there is one.
        input_tokens: Uncached input tokens.
        output_tokens: Output tokens.
        cache_read_tokens: Tokens served from the prompt cache (D5).
        cost_usd: Cost computed at call time from the rate table.
        rates_checked_on: When the rate used was last checked, so a stale
            rate is visible in the data.
        latency_ms: Wall-clock latency.
        outcome: Success, error or timeout.
        error: The error message, when the call failed.
        fallback_taken: Whether a fallback path served the call.
        created_at: When the call was made.
    """

    id: UUID
    recording_id: UUID
    stage: PipelineStage
    provider: str
    model: str
    prompt_version: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cost_usd: Decimal
    rates_checked_on: str | None = None
    latency_ms: int
    outcome: TraceOutcome
    error: str | None = None
    fallback_taken: bool = False
    created_at: datetime
