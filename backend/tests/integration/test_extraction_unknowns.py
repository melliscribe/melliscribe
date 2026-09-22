# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-007, SC-004: an unmentioned field is UNKNOWN — never a default or carry-over."""

from __future__ import annotations

from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.builders import mention_hive


def test_a_transcript_that_never_mentions_stores_yields_unknown(api):
    api.client.post("/hives", json={"identifier": "3"})
    api.extractor.output = build_output(
        hive_mentions=[mention_hive("trois", "Ruche trois")],
        temperament=heard("calm", "Elles sont calmes", 1),
    )
    api.upload("Ruche trois.\nElles sont calmes.")
    [record] = api.client.get("/records").json()
    assert record["stores"]["status"] == "unknown"
    assert record["stores"]["value"] is None
    assert record["stores"]["proposal"] is None


def test_nothing_carries_over_from_the_previous_inspection(api):
    api.client.post("/hives", json={"identifier": "3"})
    api.extractor.output = build_output(
        hive_mentions=[mention_hive("trois", "Ruche trois")],
        stores=heard("plentiful", "beaucoup de miel", 1),
    )
    api.upload("Ruche trois.\nbeaucoup de miel.")
    api.extractor.output = build_output(
        hive_mentions=[mention_hive("trois", "Ruche trois")]
    )
    api.upload("Ruche trois.")
    records = api.client.get("/records").json()
    second = next(r for r in records if r["stores"]["status"] == "unknown")
    assert second["stores"]["value"] is None
