# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""POST /recordings: idempotent on the client-generated id (FR-020)."""

from __future__ import annotations

import uuid

from sqlalchemy import func
from sqlalchemy import select

from melliscribe.db.tables import InspectionRecordRow
from melliscribe.db.tables import RecordingRow


def _count(api, table):
    with api.services.session_factory() as session:
        return session.scalar(select(func.count()).select_from(table))


def test_first_upload_is_201_and_a_repeat_is_200(api):
    recording_id = uuid.uuid4()
    first = api.upload(recording_id=recording_id)
    assert first.status_code == 201
    assert first.json()["id"] == str(recording_id)
    second = api.upload(recording_id=recording_id)
    assert second.status_code == 200
    assert _count(api, RecordingRow) == 1


def test_a_repeated_upload_never_duplicates_the_record(api):
    recording_id = uuid.uuid4()
    api.upload(recording_id=recording_id)
    api.upload(recording_id=recording_id)
    assert _count(api, InspectionRecordRow) == 1


def test_the_captured_day_is_the_device_local_day(api):
    response = api.upload(captured_at="2026-05-12T00:30:00+02:00")
    assert response.json()["captured_on"] == "2026-05-12"


def test_retention_expiry_is_set_from_the_account_setting(api):
    response = api.upload(captured_at="2026-05-12T09:30:00+00:00")
    assert response.json()["retention_expires_at"].startswith("2027-05-12")


def test_an_unsupported_format_is_415_and_nothing_is_stored(api):
    response = api.upload(audio_format="application/pdf")
    assert response.status_code == 415
    assert response.json()["code"] == "unsupported_audio_format"
    assert _count(api, RecordingRow) == 0


def test_error_messages_follow_the_account_language(api):
    """FR-025: API errors are user-facing text."""
    api.client.patch("/settings", json={"language": "en"})
    english = api.upload(audio_format="application/pdf").json()["message"]
    api.client.patch("/settings", json={"language": "fr"})
    french = api.upload(audio_format="application/pdf").json()["message"]
    assert english != french
    assert "format" in english.lower()
