# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Claude batch path, against a fake Batches API (D4, SC-007)."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from melliscribe.models.language import Language
from melliscribe.pipeline.extraction.base import BatchItem
from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.extraction.batch import ClaudeBatchExtractor
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from tests.support.builders import build_output
from tests.support.builders import build_transcript


def _message():
    return SimpleNamespace(
        stop_reason="end_turn",
        stop_details=None,
        content=[SimpleNamespace(type="text", text=build_output().model_dump_json())],
        model="claude-opus-5",
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=300,
            cache_read_input_tokens=4000,
            cache_creation_input_tokens=0,
        ),
    )


class _FakeBatches:
    def __init__(self, statuses, results):
        self.statuses = list(statuses)
        self.results_ = results
        self.created: list = []
        self.cancelled = False

    def create(self, requests):
        self.created = requests
        return SimpleNamespace(id="b1", processing_status=self.statuses.pop(0))

    def retrieve(self, batch_id):
        return SimpleNamespace(id=batch_id, processing_status=self.statuses.pop(0))

    def cancel(self, batch_id):
        self.cancelled = True
        return SimpleNamespace(id=batch_id, processing_status="canceling")

    def results(self, batch_id):
        return self.results_


def _items(count=2):
    return [
        BatchItem(
            custom_id=f"rec-{i}",
            transcript=build_transcript(f"Ruche {i}."),
            language=Language.FR,
            captured_on=date(2026, 5, 12),
        )
        for i in range(count)
    ]


def _extractor(batches, clock_values):
    clock = iter(clock_values)
    client = SimpleNamespace(messages=SimpleNamespace(batches=batches))
    sink = InMemoryTraceSink()
    extractor = ClaudeBatchExtractor(
        sink,
        client=client,  # ty: ignore[invalid-argument-type] - a fake Batches API
        sleep=lambda _: None,
        clock=lambda: next(clock),
    )
    return extractor, sink


def _result(custom_id, kind="succeeded"):
    inner = SimpleNamespace(type=kind)
    if kind == "succeeded":
        inner.message = _message()
    if kind == "errored":
        inner.error = SimpleNamespace(error=SimpleNamespace(type="overloaded_error"))
    return SimpleNamespace(custom_id=custom_id, result=inner)


def test_results_are_keyed_by_custom_id_in_any_order():
    batches = _FakeBatches(
        ["in_progress", "ended"], [_result("rec-1"), _result("rec-0")]
    )
    extractor, sink = _extractor(batches, [0, 1, 2])
    results = extractor.extract_many(_items())
    assert set(results) == {"rec-0", "rec-1"}
    assert [r["custom_id"] for r in batches.created] == ["rec-0", "rec-1"]
    assert "fallbacks" not in batches.created[0]["params"]
    assert len(sink.traces) == 2


def test_batch_traces_are_billed_at_half_price():
    batches = _FakeBatches(["ended"], [_result("rec-0")])
    extractor, sink = _extractor(batches, [0, 1])
    extractor.extract_many(_items(1))
    [trace] = sink.traces
    assert trace.provider == "anthropic-batch"
    # 100 in at $5, 300 out at $25, 4000 cache reads at $0.50, then halved.
    assert float(trace.cost_usd) == (100 * 5 + 300 * 25 + 4000 * 0.5) / 1e6 / 2


def test_the_deadline_cancels_and_leaves_unfinished_items_out():
    batches = _FakeBatches(
        ["in_progress", "in_progress", "ended"],
        [_result("rec-0"), _result("rec-1", "canceled")],
    )
    extractor, _ = _extractor(batches, [0, 10, 1000, 1001])
    results = extractor.extract_many(_items())
    assert batches.cancelled
    assert set(results) == {"rec-0"}


def test_an_errored_item_is_an_error_not_a_missing_result():
    batches = _FakeBatches(["ended"], [_result("rec-0", "errored")])
    extractor, sink = _extractor(batches, [0, 1])
    results = extractor.extract_many(_items(1))
    assert isinstance(results["rec-0"], ExtractionFailedError)
    assert sink.traces[0].outcome.value == "error"
