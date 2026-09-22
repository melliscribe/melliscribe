# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The eval runner end to end, with a scripted extractor instead of the API."""

from __future__ import annotations

from pathlib import Path

from melliscribe.evals.dataset import ExtractionCase
from melliscribe.evals.dataset import load_manifest
from melliscribe.evals.gates import check_extraction_gates
from melliscribe.evals.runner import run_extraction
from melliscribe.evals.scoring import ExtractionSummary
from melliscribe.pipeline.extraction.base import ExtractionResult
from tests.support.builders import build_output
from tests.support.builders import heard
from tests.support.builders import mention_hive
from tests.support.builders import unmentioned

SMOKE = Path(__file__).resolve().parents[2] / "evals" / "datasets" / "smoke.jsonl"


class _ScriptedExtractor:
    """Returns a perfect extraction for the sparse pair, invents stores for one."""

    def __init__(self, invent_stores=False):
        self.invent_stores = invent_stores

    def extract(self, transcript, language, captured_on):
        text = transcript.full_text
        if "micro" in text or "microphone" in text:
            output = build_output(is_inspection=False)
        else:
            segments = [s.text for s in transcript.segments]
            output = build_output(
                hive_mentions=[mention_hive("La Grise", segments[0].rstrip("."), 0)],
                temperament=heard("nervous", segments[1], 1),
                queen_seen=heard("not_looked_for", segments[2], 2),
                stores=(
                    heard("low", segments[1], 1)
                    if self.invent_stores
                    else unmentioned()
                ),
            )
        return ExtractionResult(output=output, model="scripted", prompt_version="1")


def _cases():
    return [
        c
        for c in load_manifest(SMOKE)
        if isinstance(c, ExtractionCase)
        and c.id.startswith(("smoke-sparse", "smoke-none"))
    ]


def test_a_faithful_extractor_passes_the_smoke_gates(tmp_path):
    report = run_extraction(_cases(), _ScriptedExtractor(), tmp_path)
    summary = ExtractionSummary(**report["summary"])
    assert summary.accuracy == {"fr": 100.0, "en": 100.0}
    assert check_extraction_gates(summary, baseline=None) == []


def test_an_extractor_that_invents_a_field_fails_sc004(tmp_path):
    report = run_extraction(_cases(), _ScriptedExtractor(invent_stores=True), tmp_path)
    summary = ExtractionSummary(**report["summary"])
    failures = check_extraction_gates(summary, baseline=None)
    assert any(f.startswith("SC-004") for f in failures)
    assert "smoke-sparse-fr.stores" in summary.unmentioned_populated
