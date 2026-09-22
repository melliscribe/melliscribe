# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Principle VI: cost per inspection and latency percentiles, answerable directly."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from decimal import Decimal

from melliscribe.cli.trace import percentile
from melliscribe.cli.trace import summarise
from melliscribe.db.tables import LLMTraceRow


def _row(recording_id, stage="extraction", cost="0.01", latency=1000, **extra):
    return LLMTraceRow(
        id=uuid.uuid4(),
        recording_id=recording_id,
        stage=stage,
        provider="anthropic",
        model=extra.pop("model", "claude-opus-5"),
        cost_usd=Decimal(cost),
        latency_ms=latency,
        outcome=extra.pop("outcome", "success"),
        fallback_taken=False,
        cache_read_tokens=extra.pop("cache_read_tokens", 0),
        rates_checked_on=extra.pop("rates_checked_on", "2026-06-24"),
        created_at=datetime.now(UTC),
    )


def test_percentiles():
    assert percentile([100, 200, 300, 400], 0.5) == 200
    assert percentile([100, 200, 300, 400], 0.95) == 400
    assert percentile([], 0.5) is None


def test_cost_per_recording_sums_both_stages():
    first, second = uuid.uuid4(), uuid.uuid4()
    rows = [
        _row(first, "transcription", "0.002", model="fake", rates_checked_on=None),
        _row(first, cost="0.010"),
        _row(second, cost="0.020", cache_read_tokens=3000),
    ]
    summary = summarise(rows)
    assert summary["recordings"] == 2
    assert Decimal(summary["cost_per_recording_usd"]) == Decimal("0.016")
    assert summary["unpriced_models"] == ["fake"]
    extraction = next(s for s in summary["stages"] if s["stage"] == "extraction")
    assert extraction["cache_read_tokens"] == 3000
