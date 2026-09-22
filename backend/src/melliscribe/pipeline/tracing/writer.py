# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The trace writer: one row per pipeline call (Principle VI, ADR-0006).

Deliberately thin, so it can be swapped for OpenTelemetry later without
touching the call sites. Trace rows reference a recording; they never contain
what was said (Principle III).
"""

from __future__ import annotations

import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Protocol

from melliscribe.models.trace import LLMTrace
from melliscribe.models.trace import TraceOutcome

if TYPE_CHECKING:
    from collections.abc import Iterator

    from sqlalchemy.orm import sessionmaker

    from melliscribe.models.recording import PipelineStage

_MTOK = Decimal(1_000_000)


@dataclass(frozen=True)
class Rate:
    """Per-million-token rates for one model, and when they were checked.

    A stale rate produces confidently wrong cost reporting, so the date the
    rate was last verified travels with every trace row that used it.
    """

    input_per_mtok: Decimal
    output_per_mtok: Decimal
    cache_read_per_mtok: Decimal
    cache_write_per_mtok: Decimal
    checked_on: str


RATES: dict[str, Rate] = {
    # Anthropic published rates; cache reads 0.1x, 5-minute cache writes 1.25x.
    "claude-opus-5": Rate(
        Decimal(5), Decimal(25), Decimal("0.50"), Decimal("6.25"), "2026-06-24"
    ),
    # The server-side refusal fallback model (ADR-0003).
    "claude-opus-4-8": Rate(
        Decimal(5), Decimal(25), Decimal("0.50"), Decimal("6.25"), "2026-06-24"
    ),
    # Self-hosted Whisper (ADR-0002 candidate): no per-call bill; the server's
    # running cost is outside this table.
    **{
        size: Rate(Decimal(0), Decimal(0), Decimal(0), Decimal(0), "2026-09-23")
        for size in ("tiny", "base", "small", "medium", "large-v3", "turbo")
    },
}
"""Maintained by hand. Nothing will remind anyone — check `checked_on`."""


@dataclass
class CallUsage:
    """Token usage reported by a call."""

    input_tokens: int | None = None
    output_tokens: int | None = None
    cache_read_tokens: int | None = None
    cache_write_tokens: int | None = None
    batch: bool = False
    """Served by the Batches API, billed at half price."""


BATCH_DISCOUNT = Decimal("0.5")


def compute_cost(model: str, usage: CallUsage) -> Decimal:
    """Compute a call's cost from the rate table.

    Args:
        model: The model that served the call.
        usage: The call's token usage.

    Returns:
        The cost in USD; zero for a model with no rate, which the trace row
        makes visible through a null `rates_checked_on`.
    """
    rate = RATES.get(model)
    if rate is None:
        return Decimal(0)
    cost = (
        Decimal(usage.input_tokens or 0) * rate.input_per_mtok
        + Decimal(usage.output_tokens or 0) * rate.output_per_mtok
        + Decimal(usage.cache_read_tokens or 0) * rate.cache_read_per_mtok
        + Decimal(usage.cache_write_tokens or 0) * rate.cache_write_per_mtok
    ) / _MTOK
    return cost * BATCH_DISCOUNT if usage.batch else cost


class TraceSink(Protocol):
    """Where trace rows go."""

    def write(self, trace: LLMTrace) -> None:
        """Persist one trace row.

        Args:
            trace: The row to persist.
        """


class InMemoryTraceSink:
    """Keeps traces in a list. For tests and the CLI."""

    def __init__(self) -> None:
        self.traces: list[LLMTrace] = []

    def write(self, trace: LLMTrace) -> None:
        """Append one trace row.

        Args:
            trace: The row to keep.
        """
        self.traces.append(trace)


class DatabaseTraceSink:
    """Writes each trace in its own transaction, so a failure is still recorded."""

    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory

    def write(self, trace: LLMTrace) -> None:
        """Insert one trace row and commit it.

        Args:
            trace: The row to insert.
        """
        from melliscribe.db.tables import LLMTraceRow  # noqa: PLC0415 - avoid a cycle

        with self._session_factory.begin() as session:
            session.add(LLMTraceRow(**trace.model_dump()))


@dataclass
class TracedCall:
    """What the call site reports back while the call is in flight."""

    model: str
    usage: CallUsage | None = None
    fallback_taken: bool = False
    latency_ms: int | None = None
    """Overrides the measured latency, e.g. with a batch's wall-clock time."""


@contextmanager
def trace_call(  # noqa: PLR0913 - every argument is a trace column
    sink: TraceSink,
    *,
    recording_id: uuid.UUID,
    stage: PipelineStage,
    provider: str,
    model: str,
    prompt_version: str | None = None,
) -> Iterator[TracedCall]:
    """Trace one pipeline call, whatever its outcome.

    Errors and timeouts are written to the sink and re-raised: recorded, never
    swallowed.

    Args:
        sink: Where to write the trace row.
        recording_id: The recording the call is for.
        stage: The pipeline stage making the call.
        provider: Who serves the call.
        model: The model requested; the call site may update it to the model
            that actually served the call.
        prompt_version: The prompt version, when there is one.

    Yields:
        A handle the call site fills with usage, served model and fallback.
    """
    call = TracedCall(model=model)
    outcome = TraceOutcome.SUCCESS
    error: str | None = None
    started = time.perf_counter()
    try:
        yield call
    except TimeoutError as exc:
        outcome, error = TraceOutcome.TIMEOUT, str(exc) or "timeout"
        raise
    except Exception as exc:
        outcome, error = TraceOutcome.ERROR, str(exc) or type(exc).__name__
        if "timeout" in type(exc).__name__.lower():
            outcome = TraceOutcome.TIMEOUT
        raise
    finally:
        usage = call.usage or CallUsage()
        rate = RATES.get(call.model)
        sink.write(
            LLMTrace(
                id=uuid.uuid4(),
                recording_id=recording_id,
                stage=stage,
                provider=provider,
                model=call.model,
                prompt_version=prompt_version,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cost_usd=compute_cost(call.model, usage),
                rates_checked_on=rate.checked_on if rate else None,
                latency_ms=call.latency_ms
                if call.latency_ms is not None
                else round((time.perf_counter() - started) * 1000),
                outcome=outcome,
                error=error,
                fallback_taken=call.fallback_taken,
                created_at=datetime.now(UTC),
            )
        )
