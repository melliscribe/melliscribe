# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe dev seed`: a typed transcript becomes a reviewable record."""

from __future__ import annotations

from melliscribe.cli.dev import seed_transcript
from melliscribe.models.language import Language
from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.builders import mention_hive


def test_a_typed_transcript_becomes_a_record_without_audio(api):
    api.extractor.output = build_output(
        hive_mentions=[mention_hive("trois", "Ruche trois")],
        temperament=heard("calm", "Elles sont calmes", 1),
    )
    recording_id = seed_transcript(
        api.services, ["Ruche trois.", "Elles sont calmes."], Language.FR, ["3"]
    )
    [record] = api.client.get("/records").json()
    assert record["recording_id"] == str(recording_id)
    assert record["temperament"]["value"] == "calm"
    assert record["hive"]["status"] == "system_derived"
    assert record["audio_available"] is False
    assert api.transcriber.calls == []
