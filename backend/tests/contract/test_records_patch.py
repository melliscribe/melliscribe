# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""PATCH /records/{id}: a beekeeper's edit permanently wins (FR-010, FR-022)."""

from __future__ import annotations

from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.builders import heard_text


def _record(api):
    api.extractor.output = build_output(
        temperament=heard("calm", "Elles sont calmes", 1)
    )
    recording_id = api.upload().json()["id"]
    [record] = api.client.get("/records").json()
    assert record["recording_id"] == recording_id
    return record


def test_a_patched_field_becomes_confirmed(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "temperament": "nervous"},
    )
    assert response.status_code == 200
    field = response.json()["temperament"]
    assert field["status"] == "confirmed"
    assert field["value"] == "nervous"


def test_a_confirmed_field_survives_later_extraction(api):
    record = _record(api)
    api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "temperament": "nervous", "stores": "low"},
    )
    api.extractor.output = build_output(
        temperament=heard("aggressive", "Elles sont calmes", 1)
    )
    reprocess = api.client.post(
        f"/recordings/{record['recording_id']}/reprocess", json={}
    )
    assert reprocess.status_code == 202
    after = api.client.get(f"/records/{record['id']}").json()
    assert after["temperament"]["value"] == "nervous"
    assert after["stores"]["value"] == "low"


def test_confirming_that_nothing_was_observed_is_allowed(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}", json={"version": record["version"], "stores": None}
    )
    assert response.json()["stores"] == {
        "status": "confirmed",
        "value": None,
        "proposal": None,
        "verbatim": [],
        "segment_refs": [],
        "confidence": None,
        "flag_reason": None,
    }


def test_a_stale_version_is_409(api):
    record = _record(api)
    api.client.patch(
        f"/records/{record['id']}", json={"version": record["version"], "stores": "low"}
    )
    stale = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "stores": "none"},
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "record_changed"


def test_an_unknown_vocabulary_value_is_rejected(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "temperament": "grumpy"},
    )
    assert response.status_code == 422


def test_treatments_and_actions_are_replaced_and_confirmed(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={
            "version": record["version"],
            "treatments": [{"product": "acide oxalique", "dose": "5 ml"}],
            "actions_to_do": ["poser une hausse"],
        },
    ).json()
    assert response["treatments"][0]["product"]["status"] == "confirmed"
    assert response["actions_to_do"][0]["text"]["value"] == "poser une hausse"


def test_brood_pattern_and_counts_can_be_confirmed(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={
            "version": record["version"],
            "brood_pattern": "patchy",
            "brood_frames": 5.5,
            "stores_frames": 2,
            "bee_frames": None,
        },
    ).json()
    assert response["brood_pattern"]["value"] == "patchy"
    assert response["brood_frames"] == response["brood_frames"] | {
        "status": "confirmed",
        "value": 5.5,
    }
    assert response["stores_frames"]["value"] == 2
    assert response["bee_frames"]["status"] == "confirmed"


def test_a_count_that_is_not_a_half_step_is_rejected(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "brood_frames": 3.3},
    )
    assert response.status_code == 422


def test_a_negative_count_is_rejected(api):
    record = _record(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "bee_frames": -1},
    )
    assert response.status_code == 422


def _record_with_treatment(api):
    api.extractor.output = build_output(
        treatments=[
            {
                "product": heard_text("Apivar", "deux lanières d'Apivar", 1),
                "dose": heard_text("deux lanières", "deux lanières d'Apivar", 1),
                "applied_on": "2026-05-10",
            }
        ],
        actions_to_do=[
            {
                "text": "poser une hausse",
                "confidence": 0.9,
                "phrases": [{"text": "poser une hausse", "segment_index": 1}],
                "issue": None,
            }
        ],
    )
    api.upload("Ruche trois.\nJ'ai mis deux lanières d'Apivar, poser une hausse.")
    [record] = api.client.get("/records").json()
    return record


def test_a_corrected_treatment_keeps_the_phrase_it_was_heard_as(api):
    record = _record_with_treatment(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={
            "version": record["version"],
            "treatments": [
                {"product": "Apivar", "dose": "3 lanières", "applied_on": "2026-05-10"}
            ],
        },
    ).json()
    [treatment] = response["treatments"]
    assert treatment["product"]["verbatim"] == ["deux lanières d'Apivar"]
    assert treatment["product"]["segment_refs"]
    assert treatment["dose"]["value"] == "3 lanières"
    assert treatment["applied_on"] == "2026-05-10"


def test_patching_actions_leaves_treatments_untouched(api):
    """Only what the beekeeper changed is confirmed."""
    record = _record_with_treatment(api)
    response = api.client.patch(
        f"/records/{record['id']}",
        json={"version": record["version"], "actions_to_do": ["poser une hausse"]},
    ).json()
    assert response["treatments"] == record["treatments"]
    assert response["actions_to_do"][0]["text"]["verbatim"] == ["poser une hausse"]
