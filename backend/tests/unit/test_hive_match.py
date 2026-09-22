# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FR-015: exactly one hive, flagged rather than guessed, never created."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime

import pytest

from melliscribe.domain.inspection.hive_match import normalise_identifier
from melliscribe.domain.inspection.hive_match import resolve_hive
from melliscribe.models.hive import Hive
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from tests.support.builders import build_output
from tests.support.builders import build_transcript
from tests.support.builders import mention_hive

HIVES = [
    Hive(id=uuid.uuid4(), identifier="3", created_at=datetime.now(UTC)),
    Hive(id=uuid.uuid4(), identifier="La Grise", created_at=datetime.now(UTC)),
]
TRANSCRIPT = build_transcript("Ruche trois, et puis la ruche quatre.", "La grise.")


@pytest.mark.parametrize(
    ("spoken", "expected"),
    [
        ("trois", "3"),
        ("Ruche 3", "3"),
        ("hive three", "3"),
        ("numéro 3", "3"),
        ("la grise", "la grise"),
        ("La  Grisé", "la grise"),
        ("B2", "b2"),
    ],
)
def test_identifiers_are_normalised_for_matching(spoken, expected):
    assert normalise_identifier(spoken) == expected


def test_a_single_known_hive_is_resolved():
    output = build_output(hive_mentions=[mention_hive("trois", "Ruche trois")])
    field, spoken = resolve_hive(output, TRANSCRIPT, HIVES)
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == HIVES[0].id
    assert field.verbatim == ["Ruche trois"]
    assert spoken == "trois"


def test_the_same_hive_named_twice_is_still_one_hive():
    output = build_output(
        hive_mentions=[
            mention_hive("la grise", "La grise", 1),
            mention_hive("La Grise", "La grise", 1),
        ]
    )
    field, _ = resolve_hive(output, TRANSCRIPT, HIVES)
    assert field.status is FieldStatus.SYSTEM_DERIVED
    assert field.value == HIVES[1].id


def test_an_unknown_identifier_is_flagged_and_no_hive_is_created():
    """FR-015c: parked, not invented."""
    output = build_output(hive_mentions=[mention_hive("quatre", "la ruche quatre")])
    field, spoken = resolve_hive(output, TRANSCRIPT, HIVES)
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.NO_MATCHING_HIVE
    assert field.value is None
    assert spoken == "quatre"


def test_several_hives_are_flagged_and_never_attributed_to_one():
    """FR-015e."""
    output = build_output(
        hive_mentions=[
            mention_hive("trois", "Ruche trois"),
            mention_hive("quatre", "la ruche quatre"),
        ]
    )
    field, spoken = resolve_hive(output, TRANSCRIPT, HIVES)
    assert field.status is FieldStatus.UNCERTAIN
    assert field.flag_reason is FlagReason.MULTIPLE_HIVES
    assert field.proposal is None
    assert field.verbatim == ["Ruche trois", "la ruche quatre"]
    assert spoken is None


def test_the_extractor_saying_several_hives_is_enough_to_flag():
    output = build_output(
        hive_mentions=[mention_hive("trois", "Ruche trois")], covers_multiple_hives=True
    )
    field, _ = resolve_hive(output, TRANSCRIPT, HIVES)
    assert field.flag_reason is FlagReason.MULTIPLE_HIVES


def test_no_hive_named_is_unknown():
    field, spoken = resolve_hive(build_output(), TRANSCRIPT, HIVES)
    assert field.status is FieldStatus.UNKNOWN
    assert spoken is None
