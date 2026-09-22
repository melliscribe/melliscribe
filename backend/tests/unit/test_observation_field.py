# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The flag-don't-guess invariants live in the model, not in a service."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField
from melliscribe.models.vocabulary import Temperament

TemperamentField = ObservationField[Temperament]


def test_unknown_with_a_value_is_unrepresentable():
    """SC-004's zero-tolerance criterion, enforced by a validator."""
    with pytest.raises(ValidationError, match="UNKNOWN"):
        TemperamentField(status=FieldStatus.UNKNOWN, value=Temperament.CALM)


def test_unknown_with_a_proposal_is_unrepresentable():
    with pytest.raises(ValidationError, match="UNKNOWN"):
        TemperamentField(status=FieldStatus.UNKNOWN, proposal=Temperament.CALM)


def test_unknown_without_a_value_is_valid():
    field = TemperamentField(status=FieldStatus.UNKNOWN)
    assert field.value is None
    assert field.verbatim == []


def test_uncertain_never_carries_a_set_value():
    """FR-006e: a proposal is not a value."""
    with pytest.raises(ValidationError, match="UNCERTAIN"):
        TemperamentField(
            status=FieldStatus.UNCERTAIN,
            value=Temperament.CALM,
            verbatim=["plutôt calmes"],
            flag_reason=FlagReason.LOW_CONFIDENCE,
        )


def test_uncertain_may_carry_a_proposal():
    field = TemperamentField(
        status=FieldStatus.UNCERTAIN,
        proposal=Temperament.CALM,
        verbatim=["plutôt calmes"],
        flag_reason=FlagReason.LOW_CONFIDENCE,
    )
    assert field.value is None
    assert field.proposal is Temperament.CALM


def test_uncertain_requires_a_reason():
    with pytest.raises(ValidationError, match="flag_reason"):
        TemperamentField(status=FieldStatus.UNCERTAIN, verbatim=["hmm"])


def test_system_derived_requires_a_value():
    with pytest.raises(ValidationError, match="SYSTEM_DERIVED"):
        TemperamentField(status=FieldStatus.SYSTEM_DERIVED, verbatim=["calm"])


def test_system_derived_cannot_carry_a_proposal():
    with pytest.raises(ValidationError, match="proposal"):
        TemperamentField(
            status=FieldStatus.SYSTEM_DERIVED,
            value=Temperament.CALM,
            proposal=Temperament.NERVOUS,
        )


def test_confirmed_may_be_empty():
    """A beekeeper can confirm that something was not observed."""
    field = TemperamentField(status=FieldStatus.CONFIRMED)
    assert field.value is None


def test_every_contributing_phrase_is_kept():
    """FR-006b: non-contiguous sources are all stored."""
    field = TemperamentField(
        status=FieldStatus.SYSTEM_DERIVED,
        value=Temperament.DEFENSIVE,
        verbatim=["elles sont nerveuses", "et elles piquent"],
    )
    assert field.verbatim == ["elles sont nerveuses", "et elles piquent"]
