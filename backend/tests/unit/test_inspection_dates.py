# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-016, FR-016a: the inspection date."""

from __future__ import annotations

from datetime import date

from melliscribe.domain.inspection.dates import resolve_inspection_date
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from tests.support.builders import build_output
from tests.support.builders import build_transcript

CAPTURED_ON = date(2026, 5, 12)
TRANSCRIPT = build_transcript("Visite du dix mai.", "Hier.")


def _spoken(value, phrase="Visite du dix mai", segment=0):
    return {"value": value, "phrase": {"text": phrase, "segment_index": segment}}


def test_no_spoken_date_defaults_to_the_capture_day():
    field = resolve_inspection_date(build_output(), TRANSCRIPT, CAPTURED_ON)
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == CAPTURED_ON
    assert field.verbatim == []


def test_a_spoken_date_within_a_day_wins():
    output = build_output(spoken_date=_spoken("2026-05-11", "Hier.", 1))
    field = resolve_inspection_date(output, TRANSCRIPT, CAPTURED_ON)
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == date(2026, 5, 11)
    assert field.verbatim == ["Hier."]


def test_a_spoken_date_more_than_a_day_away_is_flagged():
    output = build_output(spoken_date=_spoken("2026-05-10"))
    field = resolve_inspection_date(output, TRANSCRIPT, CAPTURED_ON)
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.DATE_CONFLICT
    assert field.proposal == date(2026, 5, 10)
    assert field.value is None
