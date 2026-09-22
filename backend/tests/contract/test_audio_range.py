# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GET /recordings/{id}/audio: range requests, and 410 once the audio is gone."""

from __future__ import annotations


def test_the_whole_file_is_served_with_its_format(api):
    recording_id = api.upload("Ruche trois.").json()["id"]
    response = api.client.get(f"/recordings/{recording_id}/audio")
    assert response.status_code == 200
    assert response.content == b"Ruche trois."
    assert response.headers["content-type"].startswith("audio/webm")
    assert response.headers["accept-ranges"] == "bytes"


def test_a_range_request_serves_the_passage(api):
    recording_id = api.upload("Ruche trois.").json()["id"]
    response = api.client.get(
        f"/recordings/{recording_id}/audio", headers={"Range": "bytes=6-10"}
    )
    assert response.status_code == 206
    assert response.content == b"trois"
    assert response.headers["content-range"] == "bytes 6-10/12"


def test_an_open_ended_range(api):
    recording_id = api.upload("Ruche trois.").json()["id"]
    response = api.client.get(
        f"/recordings/{recording_id}/audio", headers={"Range": "bytes=6-"}
    )
    assert response.content == b"trois."


def test_an_unsatisfiable_range_is_416(api):
    recording_id = api.upload("Ruche trois.").json()["id"]
    response = api.client.get(
        f"/recordings/{recording_id}/audio", headers={"Range": "bytes=50-60"}
    )
    assert response.status_code == 416


def test_deleted_audio_is_410_gone(api):
    """FR-027d: the client renders this as "no longer kept"."""
    recording_id = api.upload().json()["id"]
    assert api.client.delete(f"/recordings/{recording_id}").status_code == 204
    response = api.client.get(f"/recordings/{recording_id}/audio")
    assert response.status_code == 410
    assert response.json()["code"] == "audio_gone"
