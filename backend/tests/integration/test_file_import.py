# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""US2 scenario 1: a file the app did not record yields the same record (FR-005)."""

from __future__ import annotations

import pytest

from tests.support.builders import build_output
from tests.support.builders import heard


@pytest.mark.parametrize("audio_format", ["audio/mpeg", "audio/x-m4a", "audio/wav"])
def test_an_imported_file_is_processed_like_a_dictation(api, audio_format):
    api.extractor.output = build_output(
        temperament=heard("calm", "Elles sont calmes", 1)
    )
    live = api.upload("Ruche trois.\nElles sont calmes.")
    imported = api.upload("Ruche trois.\nElles sont calmes.", audio_format=audio_format)
    assert imported.status_code == 201
    records = {r["recording_id"]: r for r in api.client.get("/records").json()}
    first = records[live.json()["id"]]
    second = records[imported.json()["id"]]
    for name in ("queen_seen", "brood", "stores", "temperament", "hive"):
        assert first[name]["status"] == second[name]["status"]
        assert first[name]["value"] == second[name]["value"]


def test_an_unsupported_file_is_refused_with_a_clear_message(api):
    response = api.upload(audio_format="video/quicktime")
    assert response.status_code == 415
    assert "video/quicktime" in response.json()["message"]
