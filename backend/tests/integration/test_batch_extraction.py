# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""US2: a backlog extracts through the Batch API, one record per recording (D4)."""

from __future__ import annotations

from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.queue import run_queue_once
from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.fakes import FakeBatchExtractor


def _backlog(api, count=3):
    api.services.process_on_upload = False
    api.services.batch_extractor = FakeBatchExtractor(api.extractor)
    api.extractor.output = build_output(
        temperament=heard("calm", "Elles sont calmes", 1)
    )
    return [
        api.upload(f"Ruche {i}.\nElles sont calmes.").json()["id"] for i in range(count)
    ]


def test_each_queued_recording_gets_its_own_record(api):
    ids = _backlog(api)
    run_queue_once(api.services)
    records = api.client.get("/records").json()
    assert sorted(r["recording_id"] for r in records) == sorted(ids)
    [batch] = api.services.batch_extractor.batches
    assert sorted(batch) == sorted(ids)


def test_results_are_keyed_by_custom_id_not_position(api):
    ids = _backlog(api)
    run_queue_once(api.services)
    for recording_id in ids:
        [record] = [
            r
            for r in api.client.get("/records").json()
            if r["recording_id"] == recording_id
        ]
        transcript_text = record["transcript"]["segments"][0]["text"]
        index = ids.index(recording_id)
        assert transcript_text == f"Ruche {index}."


def test_the_custom_id_is_the_client_generated_recording_id(api):
    ids = _backlog(api)
    run_queue_once(api.services)
    assert set(api.services.batch_extractor.batches[0]) == set(ids)


def test_an_unanswered_item_falls_back_to_live_extraction(api):
    """SC-007: a slow batch never leaves a recording waiting past the deadline."""
    ids = _backlog(api)
    api.services.batch_extractor.unanswered = {ids[1]}
    run_queue_once(api.services)
    assert len(api.client.get("/records").json()) == 3


def test_a_failed_item_fails_alone_at_the_extraction_stage(api):
    ids = _backlog(api)
    api.services.batch_extractor.errors = {ids[0]: ExtractionFailedError("refused")}
    run_queue_once(api.services)
    failed = api.client.get(f"/recordings/{ids[0]}").json()
    assert failed["state"] == "failed"
    assert failed["failure_stage"] == "extraction"
    assert len(api.client.get("/records").json()) == 2


def test_a_single_recording_is_extracted_live(api):
    _backlog(api, count=1)
    run_queue_once(api.services)
    assert api.services.batch_extractor.batches == []
    assert len(api.client.get("/records").json()) == 1


def test_a_recording_is_never_processed_twice(api):
    _backlog(api, count=2)
    run_queue_once(api.services)
    run_queue_once(api.services)
    assert len(api.services.batch_extractor.batches) == 1
