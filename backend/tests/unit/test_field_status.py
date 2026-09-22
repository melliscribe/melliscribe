# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-007, FR-008, FR-006d-f: how an extracted observation becomes a field."""

from __future__ import annotations

from melliscribe.domain.inspection.status import assign_status
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.vocabulary import Temperament
from melliscribe.pipeline.extraction.schema import ExtractedObservation
from melliscribe.pipeline.extraction.thresholds import UNCERTAINTY_THRESHOLD
from tests.support.builders import build_transcript
from tests.support.builders import heard
from tests.support.builders import unmentioned

TRANSCRIPT = build_transcript("Ruche trois.", "Elles sont calmes aujourd'hui.")


def _assign(data):
    observation = ExtractedObservation[Temperament].model_validate(data)
    return assign_status(observation, TRANSCRIPT)


def test_unmentioned_is_unknown_with_no_value():
    field = _assign(unmentioned())
    assert field.status is FieldStatus.UNKNOWN
    assert field.value is None


def test_unmentioned_stays_unknown_even_if_a_value_leaks_through():
    """SC-004: a value on an unmentioned field is discarded, not trusted."""
    data = unmentioned() | {"value": "calm", "confidence": 0.99}
    field = _assign(data)
    assert field.status is FieldStatus.UNKNOWN
    assert field.value is None


def test_confident_and_quoted_is_system_derived():
    field = _assign(heard("calm", "Elles sont calmes", segment=1))
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value is Temperament.CALM
    assert field.verbatim == ["Elles sont calmes"]
    assert field.segment_refs[0].segment_index == 1
    assert field.segment_refs[0].start_seconds == 5.0


def test_below_threshold_is_uncertain_with_a_proposal():
    field = _assign(
        heard("calm", "Elles sont calmes", 1, confidence=UNCERTAINTY_THRESHOLD - 0.01)
    )
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.LOW_CONFIDENCE
    assert field.value is None
    assert field.proposal is Temperament.CALM


def test_unmappable_is_uncertain_keeping_the_verbatim():
    """FR-006d: never forced into the nearest value."""
    field = _assign(heard(None, "Elles sont calmes", 1, issue="unmappable"))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.UNMAPPABLE
    assert field.proposal is None
    assert field.verbatim == ["Elles sont calmes"]


def test_mentioned_without_a_value_is_unmappable_even_without_an_issue():
    field = _assign(heard(None, "Elles sont calmes", 1))
    assert field.flag_reason is FlagReason.UNMAPPABLE


def test_an_unclear_correction_is_flagged():
    """FR-006f."""
    field = _assign(heard("calm", "Elles sont calmes", 1, issue="unclear_correction"))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.UNCLEAR_CORRECTION


def test_a_phrase_in_the_other_language_is_flagged():
    """FR-026f."""
    field = _assign(heard("calm", "Elles sont calmes", 1, issue="other_language"))
    assert field.flag_reason is FlagReason.OTHER_LANGUAGE


def test_an_unknown_term_is_flagged_not_failed():
    """FR-014b."""
    field = _assign(heard("calm", "Elles sont calmes", 1, issue="unknown_term"))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.UNKNOWN_TERM


def test_a_phrase_absent_from_the_transcript_is_not_trusted():
    """A value whose quote cannot be found may be invented: flag it."""
    field = _assign(heard("calm", "très douces", 1))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.LOW_CONFIDENCE
    assert field.proposal is Temperament.CALM


def test_a_mentioned_field_with_no_phrase_is_not_trusted():
    data = heard("calm", "x") | {"phrases": []}
    field = _assign(data)
    assert field.status is FieldStatus.UNCERTAIN


def test_quote_matching_ignores_case_and_spacing():
    field = _assign(heard("calm", "elles  sont CALMES", 1))
    assert field.status is FieldStatus.SYSTEM_DERIVED


def test_an_out_of_range_segment_keeps_the_phrase_but_not_the_ref():
    field = _assign(heard("calm", "Elles sont calmes", 9))
    assert field.verbatim == ["Elles sont calmes"]
    assert field.segment_refs == []
