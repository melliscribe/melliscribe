# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-023: a field's segment reference is where its phrase was spoken."""

from __future__ import annotations

from tests.support.builders import build_output
from tests.support.builders import heard


def test_each_populated_field_points_at_its_segment(api):
    api.extractor.output = build_output(
        queen_seen=heard("seen", "Reine vue", 1),
        temperament=heard("calm", "Elles sont calmes", 2),
    )
    api.upload("Ruche trois.\nReine vue.\nElles sont calmes.")
    [record] = api.client.get("/records").json()
    segments = record["transcript"]["segments"]
    for name, phrase in (
        ("queen_seen", "Reine vue"),
        ("temperament", "Elles sont calmes"),
    ):
        [ref] = record[name]["segment_refs"]
        segment = segments[ref["segment_index"]]
        assert phrase in segment["text"]
        assert ref["start_seconds"] == segment["start_seconds"]
        assert ref["end_seconds"] == segment["end_seconds"]
