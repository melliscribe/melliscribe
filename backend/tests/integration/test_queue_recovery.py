# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""A pass that dies never strands a recording (FR-019)."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta

from sqlalchemy import update

from melliscribe.db.tables import RecordingRow
from melliscribe.pipeline import queue
from melliscribe.pipeline.queue import STALE_AFTER
from melliscribe.pipeline.queue import run_queue_once
from tests.support.fakes import FakeBatchExtractor


class _UnreachableBatches(FakeBatchExtractor):
    def extract_many(self, items):
        raise ConnectionError("down")


def _park(api, state, age):
    """Upload without processing, then pretend a pass left it in `state`."""
    api.services.process_on_upload = False
    recording_id = api.upload().json()["id"]
    with api.services.session_factory.begin() as session:
        session.execute(
            update(RecordingRow)
            .where(RecordingRow.id == uuid.UUID(recording_id))
            .values(state=state, state_changed_at=datetime.now(UTC) - age)
        )
    return recording_id


def test_a_recording_stranded_mid_pass_is_picked_up_again(api):
    recording_id = _park(api, "transcribing", STALE_AFTER + timedelta(minutes=1))
    assert run_queue_once(api.services) == 1
    assert api.client.get(f"/recordings/{recording_id}").json()["state"] == "processed"


def test_a_recording_in_flight_is_left_alone(api):
    recording_id = _park(api, "extracting", timedelta(minutes=1))
    assert run_queue_once(api.services) == 0
    assert api.client.get(f"/recordings/{recording_id}").json()["state"] == "extracting"


def test_an_unexpected_error_fails_that_recording_only(api, monkeypatch):
    api.services.process_on_upload = False
    broken = api.upload().json()["id"]
    fine = api.upload().json()["id"]
    real = queue.process_recording

    def flaky(services, recording_id, **kwargs):
        if str(recording_id) == broken:
            raise RuntimeError("database went away")
        return real(services, recording_id, **kwargs)

    monkeypatch.setattr(queue, "process_recording", flaky)
    run_queue_once(api.services)
    failed = api.client.get(f"/recordings/{broken}").json()
    assert failed["state"] == "failed"
    assert "database went away" in failed["failure_reason"]
    assert api.client.get(f"/recordings/{fine}").json()["state"] == "processed"


def test_a_batch_that_cannot_be_submitted_falls_back_to_live(api):
    api.services.process_on_upload = False
    api.services.batch_extractor = _UnreachableBatches(api.extractor)
    ids = [api.upload().json()["id"] for _ in range(2)]
    run_queue_once(api.services)
    for recording_id in ids:
        assert (
            api.client.get(f"/recordings/{recording_id}").json()["state"] == "processed"
        )


def test_state_changes_are_timestamped(api):
    recording = api.upload().json()
    with api.services.session_factory() as session:
        row = session.get(RecordingRow, uuid.UUID(recording["id"]))
        assert row.state_changed_at is not None
