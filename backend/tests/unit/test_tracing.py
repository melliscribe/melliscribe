# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Principle VI: every call is traced, and failures are recorded, not swallowed."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest

from melliscribe.models.recording import PipelineStage
from melliscribe.models.trace import TraceOutcome
from melliscribe.pipeline.tracing.writer import RATES
from melliscribe.pipeline.tracing.writer import CallUsage
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from melliscribe.pipeline.tracing.writer import compute_cost
from melliscribe.pipeline.tracing.writer import trace_call


class _BoomError(RuntimeError):
    pass


def test_a_successful_call_writes_a_success_row():
    sink = InMemoryTraceSink()
    recording_id = uuid.uuid4()
    with trace_call(
        sink,
        recording_id=recording_id,
        stage=PipelineStage.EXTRACTION,
        provider="anthropic",
        model="claude-opus-5",
        prompt_version="1",
    ) as call:
        call.usage = CallUsage(
            input_tokens=1000, output_tokens=200, cache_read_tokens=5000
        )
    [trace] = sink.traces
    assert trace.outcome is TraceOutcome.SUCCESS
    assert trace.recording_id == recording_id
    assert trace.cache_read_tokens == 5000
    assert trace.cost_usd > 0
    assert trace.rates_checked_on is not None


def test_an_error_writes_an_error_row_and_is_re_raised():
    sink = InMemoryTraceSink()
    with (
        pytest.raises(_BoomError),
        trace_call(
            sink,
            recording_id=uuid.uuid4(),
            stage=PipelineStage.EXTRACTION,
            provider="anthropic",
            model="claude-opus-5",
        ),
    ):
        raise _BoomError("bad request")
    [trace] = sink.traces
    assert trace.outcome is TraceOutcome.ERROR
    assert trace.error == "bad request"


def test_a_timeout_writes_a_timeout_row_and_is_re_raised():
    sink = InMemoryTraceSink()
    with (
        pytest.raises(TimeoutError),
        trace_call(
            sink,
            recording_id=uuid.uuid4(),
            stage=PipelineStage.TRANSCRIPTION,
            provider="fake",
            model="fake",
        ),
    ):
        raise TimeoutError
    [trace] = sink.traces
    assert trace.outcome is TraceOutcome.TIMEOUT


def test_a_fallback_is_recorded():
    sink = InMemoryTraceSink()
    with trace_call(
        sink,
        recording_id=uuid.uuid4(),
        stage=PipelineStage.EXTRACTION,
        provider="anthropic",
        model="claude-opus-5",
    ) as call:
        call.fallback_taken = True
        call.model = "claude-opus-4-8"
    [trace] = sink.traces
    assert trace.fallback_taken
    assert trace.model == "claude-opus-4-8"


def test_cost_uses_the_cached_rate_for_cache_reads():
    rate = RATES["claude-opus-5"]
    cost = compute_cost(
        "claude-opus-5",
        CallUsage(input_tokens=0, output_tokens=0, cache_read_tokens=1_000_000),
    )
    assert cost == rate.cache_read_per_mtok


def test_an_unknown_model_costs_zero_and_says_so():
    cost = compute_cost("mystery", CallUsage(input_tokens=10, output_tokens=10))
    assert cost == Decimal(0)
