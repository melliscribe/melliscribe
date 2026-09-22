# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-006j, FR-006k: frame counts are taken as said, and doubt is flagged."""

from __future__ import annotations

import pytest

from melliscribe.domain.inspection.counts import FRAME_COUNT_LIMIT
from melliscribe.domain.inspection.counts import assign_count
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.pipeline.extraction.schema import ExtractedCount
from tests.support.builders import build_transcript
from tests.support.builders import counted
from tests.support.builders import uncounted

TRANSCRIPT = build_transcript(
    "Ruche trois.",
    "Du couvain sur cinq cadres et demi.",
    "Quatre ou cinq cadres de miel.",
    "Dix faces de couvain.",
)


def _assign(data):
    return assign_count(ExtractedCount.model_validate(data), TRANSCRIPT)


def test_an_unmentioned_count_is_unknown():
    field = _assign(uncounted())
    assert field.status is FieldStatus.UNKNOWN
    assert field.value is None


def test_a_count_in_half_frames_is_kept_with_its_phrase():
    field = _assign(counted(5.5, "Du couvain sur cinq cadres et demi", 1))
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == 5.5
    assert field.verbatim == ["Du couvain sur cinq cadres et demi"]
    assert field.segment_refs[0].segment_index == 1


def test_a_count_of_faces_is_converted_to_frames_keeping_the_words():
    field = _assign(counted(10, "Dix faces de couvain", 3, unit="faces"))
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == 5
    assert field.verbatim == ["Dix faces de couvain"]


def test_an_odd_number_of_faces_gives_a_half_frame():
    field = _assign(counted(7, "Dix faces de couvain", 3, unit="faces"))
    assert field.value == 3.5


def test_a_count_that_is_not_a_half_step_is_flagged():
    field = _assign(counted(3.3, "Du couvain sur cinq cadres et demi", 1))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.IMPLAUSIBLE_COUNT
    assert field.proposal is None


def test_an_approximate_count_is_flagged_with_no_suggested_number():
    """US1/AC20: flagged rather than rounded, and no proposal."""
    field = _assign(counted(4.5, "Quatre ou cinq cadres de miel", 2, approximate=True))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.APPROXIMATE_COUNT
    assert field.value is None
    assert field.proposal is None
    assert field.verbatim == ["Quatre ou cinq cadres de miel"]


def test_a_count_above_the_limit_is_flagged_not_stored():
    """US1/AC24."""
    field = _assign(counted(FRAME_COUNT_LIMIT + 10, "Du couvain sur cinq cadres", 1))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.IMPLAUSIBLE_COUNT
    assert field.proposal is None


def test_the_limit_itself_is_accepted():
    field = _assign(counted(FRAME_COUNT_LIMIT, "Du couvain sur cinq cadres", 1))
    assert field.status is FieldStatus.SYSTEM_DERIVED


@pytest.mark.parametrize("value", [-1, -0.5])
def test_a_negative_count_is_never_stored(value):
    field = _assign(counted(value, "Du couvain sur cinq cadres", 1))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.value is None
    assert field.proposal is None


def test_a_count_heard_without_a_number_is_flagged():
    field = _assign(counted(None, "Du couvain sur cinq cadres", 1))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.UNMAPPABLE


def test_a_low_confidence_count_may_carry_a_proposal():
    field = _assign(counted(5, "Du couvain sur cinq cadres", 1, confidence=0.3))
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.LOW_CONFIDENCE
    assert field.proposal == 5


def test_a_count_whose_phrase_is_not_in_the_transcript_is_not_trusted():
    field = _assign(counted(6, "six cadres de couvain", 1))
    assert field.status is FieldStatus.UNCERTAIN
