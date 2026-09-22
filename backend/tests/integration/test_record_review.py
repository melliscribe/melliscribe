# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Review, hive resolution, confirmation, language and failure handling (US1)."""

from __future__ import annotations

from melliscribe.pipeline.extraction.base import ExtractionFailedError
from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.builders import mention_hive


def _upload_one(api, output=None, text="Ruche quatre.\nElles sont calmes."):
    api.extractor.output = output or build_output(
        hive_mentions=[mention_hive("quatre", "Ruche quatre")],
        temperament=heard("calm", "Elles sont calmes", 1),
    )
    return api.upload(text).json()


def test_a_record_carries_status_verbatim_segments_and_transcript(api):
    _upload_one(api)
    [summary] = api.client.get("/records").json()
    record = api.client.get(f"/records/{summary['id']}").json()
    assert record["temperament"]["verbatim"] == ["Elles sont calmes"]
    assert record["temperament"]["segment_refs"][0]["start_seconds"] == 5.0
    assert [s["text"] for s in record["transcript"]["segments"]] == [
        "Ruche quatre.",
        "Elles sont calmes.",
    ]
    assert record["audio_available"] is True
    assert "confidence" in record["temperament"]


def test_an_unmatched_hive_is_resolved_by_creating_it_from_review(api):
    """FR-015b, FR-015c: parked, then created by an explicit action."""
    _upload_one(api)
    [record] = api.client.get("/records").json()
    assert record["hive"]["flag_reason"] == "no_matching_hive"
    assert record["spoken_hive_identifier"] == "quatre"
    assert api.client.get("/hives").json() == []
    resolved = api.client.post(
        f"/records/{record['id']}/resolve-hive", json={"identifier": "Ruche 4"}
    )
    assert resolved.status_code == 200
    [hive] = api.client.get("/hives").json()
    assert resolved.json()["hive"] == {
        "status": "confirmed",
        "value": hive["id"],
        "proposal": None,
        "verbatim": ["Ruche quatre"],
        "segment_refs": resolved.json()["hive"]["segment_refs"],
        "confidence": None,
        "flag_reason": None,
    }


def test_a_hive_can_be_resolved_to_an_existing_one(api):
    hive = api.client.post("/hives", json={"identifier": "B2"}).json()
    _upload_one(api)
    [record] = api.client.get("/records").json()
    resolved = api.client.post(
        f"/records/{record['id']}/resolve-hive", json={"hive_id": hive["id"]}
    ).json()
    assert resolved["hive"]["value"] == hive["id"]


def test_confirming_a_record_with_open_flags_is_refused(api):
    _upload_one(api)
    [record] = api.client.get("/records").json()
    response = api.client.post(f"/records/{record['id']}/confirm")
    assert response.status_code == 409
    assert response.json()["code"] == "record_has_open_flags"


def test_confirming_a_record_confirms_its_derived_values(api):
    hive = api.client.post("/hives", json={"identifier": "4"}).json()
    _upload_one(api)
    [record] = api.client.get("/records").json()
    assert record["hive"]["value"] == hive["id"]
    assert record["confirmed_at"] is None
    confirmed = api.client.post(f"/records/{record['id']}/confirm").json()
    assert confirmed["confirmed_at"] is not None
    assert confirmed["temperament"]["status"] == "confirmed"
    assert confirmed["stores"]["status"] == "unknown"


def test_an_empty_dictation_produces_no_record_and_keeps_the_recording(api):
    """FR-016b."""
    body = _upload_one(api, build_output(is_inspection=False), "Test, un deux trois.")
    assert api.client.get("/records").json() == []
    recording = api.client.get(f"/recordings/{body['id']}").json()
    assert recording["state"] == "no_inspection"
    assert recording["audio_available"] is True


def test_a_transcription_failure_keeps_the_recording_and_names_the_stage(api):
    """FR-019, FR-019b."""
    api.transcriber.fail_with = RuntimeError("asr down")
    body = api.upload().json()
    recording = api.client.get(f"/recordings/{body['id']}").json()
    assert recording["state"] == "failed"
    assert recording["failure_stage"] == "transcription"
    assert "asr down" in recording["failure_reason"]
    assert api.services.audio_store.read(body["id"])


def test_an_extraction_failure_keeps_the_transcript(api):
    """FR-019a: the transcript is retained and retryable on its own."""
    api.extractor.fail_with = ExtractionFailedError("refused")
    body = api.upload().json()
    recording = api.client.get(f"/recordings/{body['id']}").json()
    assert recording["failure_stage"] == "extraction"
    api.extractor.fail_with = None
    api.client.post(f"/recordings/{body['id']}/retry")
    assert len(api.transcriber.calls) == 1
    assert api.client.get(f"/recordings/{body['id']}").json()["state"] == "processed"


def test_a_failed_reprocess_keeps_the_previous_record(api):
    """FR-019c."""
    body = _upload_one(api)
    [before] = api.client.get("/records").json()
    api.extractor.fail_with = ExtractionFailedError("refused")
    api.client.post(f"/recordings/{body['id']}/reprocess", json={"language": "en"})
    [after] = api.client.get("/records").json()
    assert after["temperament"] == before["temperament"]
    recording = api.client.get(f"/recordings/{body['id']}").json()
    assert recording["reprocess_failed"] is True
    assert recording["state"] == "processed"


def test_a_language_correction_retranscribes_in_the_new_language(api):
    """FR-026b."""
    body = _upload_one(api)
    api.client.post(f"/recordings/{body['id']}/reprocess", json={"language": "en"})
    assert [lang.value for lang in api.transcriber.calls] == ["fr", "en"]
    [record] = api.client.get("/records").json()
    assert record["language"] == "en"


def test_a_detected_language_disagreement_is_shown_not_acted_on(api):
    """FR-026e."""
    _upload_one(
        api,
        build_output(
            temperament=heard("calm", "Elles sont calmes", 1), detected_language="en"
        ),
    )
    [record] = api.client.get("/records").json()
    assert record["language"] == "fr"
    assert record["detected_language"] == "en"


def test_every_call_is_traced(api):
    _upload_one(api)
    assert [t.stage.value for t in api.traces.traces] == ["transcription"]
