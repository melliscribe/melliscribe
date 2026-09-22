# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-002, FR-003 server side: 201/200 only once the audio is durable.

The client's half — IndexedDB before confirming, never dropping before an
acknowledgement — is tested in the frontend suite.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy import select

from melliscribe.db.tables import RecordingRow


def test_the_audio_is_on_disk_when_201_is_returned(api):
    response = api.upload("Ruche trois.")
    assert response.status_code == 201
    assert api.services.audio_store.read(response.json()["id"]) == b"Ruche trois."


def test_a_failed_audio_write_is_never_acknowledged(api, monkeypatch):
    def broken_write(recording_id, data):
        raise OSError("disk full")

    monkeypatch.setattr(api.services.audio_store, "write", broken_write)
    response = api.upload()
    assert response.status_code == 503
    assert response.json()["code"] == "storage_unavailable"
    with api.services.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(RecordingRow)) == 0


def test_the_state_leaves_pending_upload_on_acknowledgement(api):
    body = api.upload().json()
    assert body["state"] != "pending_upload"
