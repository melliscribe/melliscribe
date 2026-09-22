# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The eval harness's own scoring must be right, or the gate is decoration."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from melliscribe.evals.dataset import ExtractionCase
from melliscribe.evals.gates import check_extraction_gates
from melliscribe.evals.gates import check_transcription_gates
from melliscribe.evals.scoring import CaseOutcome
from melliscribe.evals.scoring import compute_word_error_rate
from melliscribe.evals.scoring import find_glossary_hits
from melliscribe.evals.scoring import score_case
from melliscribe.evals.scoring import summarise_extraction
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import ObservationField
from melliscribe.models.vocabulary import Temperament


def _case(language="fr", pair_id=None, **expected):
    return ExtractionCase.model_validate(
        {
            "id": f"case-{language}-{pair_id}",
            "stage": "extraction",
            "language": language,
            "pair_id": pair_id,
            "purpose_made": True,
            "captured_on": "2026-05-12",
            "hives": ["3"],
            "segments": [
                {"text": "Ruche trois.", "start_seconds": 0, "end_seconds": 1}
            ],
            "expected": {"is_inspection": True, "fields": expected},
        }
    )


def test_a_case_needs_a_consent_reference_or_a_purpose_made_marker():
    """FR-027f: provenance is auditable, not asserted."""
    with pytest.raises(ValidationError, match="consent"):
        ExtractionCase.model_validate(
            _case().model_dump() | {"purpose_made": False, "consent_ref": None}
        )


def test_a_value_on_an_expected_unknown_field_is_an_sc004_violation():
    case = _case(temperament={"status": "unknown"})
    fields = {
        "temperament": ObservationField[Temperament](
            status=FieldStatus.SYSTEM_DERIVED, value=Temperament.CALM
        )
    }
    outcome = score_case(case, fields)
    assert outcome.unmentioned_populated == ["temperament"]
    assert outcome.correct == {"temperament": False}


def test_a_proposal_on_an_expected_unknown_field_is_also_a_violation():
    case = _case(temperament={"status": "unknown"})
    fields = {
        "temperament": ObservationField[Temperament](
            status=FieldStatus.UNCERTAIN,
            proposal=Temperament.CALM,
            verbatim=["x"],
            flag_reason="low_confidence",
        )
    }
    assert score_case(case, fields).unmentioned_populated == ["temperament"]


def test_a_right_value_with_the_wrong_status_is_not_accurate():
    """SC-005: status is part of correctness."""
    case = _case(temperament={"status": "system_derived", "value": "calm"})
    fields = {
        "temperament": ObservationField[Temperament](
            status=FieldStatus.UNCERTAIN,
            proposal=Temperament.CALM,
            verbatim=["x"],
            flag_reason="low_confidence",
        )
    }
    assert score_case(case, fields).correct == {"temperament": False}


def test_matching_status_and_value_is_accurate():
    case = _case(temperament={"status": "system_derived", "value": "calm"})
    fields = {
        "temperament": ObservationField[Temperament](
            status=FieldStatus.SYSTEM_DERIVED, value=Temperament.CALM, verbatim=["x"]
        )
    }
    assert score_case(case, fields).correct == {"temperament": True}


def test_a_missing_record_scores_every_field_wrong():
    case = _case(temperament={"status": "system_derived", "value": "calm"})
    outcome = score_case(case, None)
    assert outcome.correct == {"temperament": False}
    assert not outcome.is_inspection_correct


def test_summary_computes_per_language_accuracy_and_parity():
    outcomes = [
        CaseOutcome("a", "fr", "p1", {"x": True, "y": True}, [], True, {"x": "calm"}),
        CaseOutcome("b", "en", "p1", {"x": True, "y": False}, [], True, {"x": "calm"}),
    ]
    summary = summarise_extraction(outcomes)
    # Whether a record was produced at all counts as one more judgement.
    assert summary.accuracy == {"fr": 100.0, "en": 66.67}
    assert summary.parity_gap == 33.33
    assert summary.paired_disagreements == []


def test_paired_cases_with_different_coded_values_disagree():
    """SC-011."""
    outcomes = [
        CaseOutcome("a", "fr", "p1", {"x": True}, [], True, {"x": "calm"}),
        CaseOutcome("b", "en", "p1", {"x": False}, [], True, {"x": "nervous"}),
    ]
    assert summarise_extraction(outcomes).paired_disagreements == ["p1.x"]


def test_word_error_rate():
    assert compute_word_error_rate("la ruche est calme", "la ruche est calme") == 0.0
    assert compute_word_error_rate("la ruche est calme", "la housse est calme") == 25.0


def test_glossary_hits_ignore_case_and_accents():
    assert find_glossary_hits(["hausse", "couvain"], "Poser une HAUSSE demain") == {
        "hausse": True,
        "couvain": False,
    }


def test_extraction_gates():
    outcomes = [
        CaseOutcome("a", "fr", None, {"x": True}, ["y"], True, {}),
    ]
    summary = summarise_extraction(outcomes)
    failures = check_extraction_gates(summary, baseline=None)
    assert any("SC-004" in f for f in failures)


def test_an_accuracy_regression_against_the_baseline_blocks():
    outcomes = [CaseOutcome("a", "fr", None, {"x": False}, [], True, {})]
    baseline = summarise_extraction(
        [CaseOutcome("a", "fr", None, {"x": True}, [], True, {})]
    )
    failures = check_extraction_gates(summarise_extraction(outcomes), baseline)
    assert any("regressed" in f for f in failures)


def test_transcription_gates_require_glossary_recall():
    failures = check_transcription_gates({"fr": 10.0}, {"fr": 80.0}, baseline_wer=None)
    assert any("SC-010" in f for f in failures)
