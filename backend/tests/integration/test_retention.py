# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""US4: the record outlives the audio (FR-027b, FR-027c)."""

from __future__ import annotations

from tests.support.builders import build_output
from tests.support.builders import heard


def test_deleting_audio_keeps_the_record_and_transcript(api):
    api.extractor.output = build_output(
        temperament=heard("calm", "Elles sont calmes", 1)
    )
    recording_id = api.upload("Ruche trois.\nElles sont calmes.").json()["id"]
    [before] = api.client.get("/records").json()
    assert api.client.delete(f"/recordings/{recording_id}").status_code == 204
    [after] = api.client.get("/records").json()
    assert after["temperament"]["verbatim"] == ["Elles sont calmes"]
    assert after["transcript"] == before["transcript"]
    assert after["audio_available"] is False
    recording = api.client.get(f"/recordings/{recording_id}").json()
    assert recording["audio_available"] is False
    assert recording["retention_expires_at"] is None
    assert not api.services.audio_store.get_path(recording_id).exists()


def test_deletion_ignores_the_retention_setting(api):
    recording_id = api.upload().json()["id"]
    api.client.patch("/settings", json={"audio_retention_days": 3650})
    assert api.client.delete(f"/recordings/{recording_id}").status_code == 204


def test_changing_the_retention_period_moves_existing_expiries(api):
    recording_id = api.upload(captured_at="2026-05-12T09:30:00+00:00").json()["id"]
    api.client.patch("/settings", json={"audio_retention_days": 30})
    recording = api.client.get(f"/recordings/{recording_id}").json()
    assert recording["retention_expires_at"].startswith("2026-06-11")
