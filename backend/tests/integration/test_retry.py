# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-019, FR-019a: retry without re-recording, reusing a transcript that succeeded."""

from __future__ import annotations

from melliscribe.pipeline.extraction.base import ExtractionFailedError


def test_retry_after_extraction_failure_does_not_transcribe_again(api):
    api.extractor.fail_with = ExtractionFailedError("overloaded")
    recording_id = api.upload().json()["id"]
    api.extractor.fail_with = None
    assert api.client.post(f"/recordings/{recording_id}/retry").status_code == 202
    assert len(api.transcriber.calls) == 1
    assert len(api.client.get("/records").json()) == 1


def test_retry_after_transcription_failure_transcribes(api):
    api.transcriber.fail_with = RuntimeError("asr down")
    recording_id = api.upload().json()["id"]
    api.transcriber.fail_with = None
    api.client.post(f"/recordings/{recording_id}/retry")
    assert api.client.get(f"/recordings/{recording_id}").json()["state"] == "processed"


def test_only_a_failed_recording_can_be_retried(api):
    recording_id = api.upload().json()["id"]
    response = api.client.post(f"/recordings/{recording_id}/retry")
    assert response.status_code == 409
    assert response.json()["code"] == "not_retryable"


def test_the_failed_list_is_filterable(api):
    api.transcriber.fail_with = RuntimeError("asr down")
    api.upload()
    api.transcriber.fail_with = None
    api.upload()
    failed = api.client.get("/recordings", params={"state": "failed"}).json()
    assert len(failed) == 1
