# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GET/PATCH /settings (FR-026, FR-027a)."""

from __future__ import annotations


def test_defaults(api):
    assert api.client.get("/settings").json() == {
        "language": "fr",
        "audio_retention_days": 365,
    }


def test_language_is_never_inferred_from_the_request(api):
    response = api.client.get("/settings", headers={"Accept-Language": "en-GB"})
    assert response.json()["language"] == "fr"


def test_update(api):
    response = api.client.patch(
        "/settings", json={"language": "en", "audio_retention_days": 30}
    )
    assert response.json() == {"language": "en", "audio_retention_days": 30}
    assert api.client.get("/settings").json()["language"] == "en"


def test_invalid_retention_is_rejected(api):
    assert (
        api.client.patch("/settings", json={"audio_retention_days": 0}).status_code
        == 422
    )


def test_eval_consent_is_recorded_with_its_date_and_can_be_withdrawn(api):
    """FR-027f: explicit, separate, per recording, dated."""
    recording_id = api.upload().json()["id"]
    recording = api.client.get(f"/recordings/{recording_id}").json()
    assert recording["eval_consent_at"] is None
    given = api.client.post(
        f"/recordings/{recording_id}/eval-consent", json={"consented": True}
    ).json()
    assert given["eval_consent_at"] is not None
    withdrawn = api.client.post(
        f"/recordings/{recording_id}/eval-consent", json={"consented": False}
    ).json()
    assert withdrawn["eval_consent_at"] is None
