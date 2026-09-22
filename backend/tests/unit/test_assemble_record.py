# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assembling a record, and re-processing without losing confirmed work."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import date
from datetime import datetime

from melliscribe.domain.inspection.assemble import AssemblyContext
from melliscribe.domain.inspection.assemble import assemble_record as _assemble
from melliscribe.models.hive import Hive
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField
from melliscribe.models.language import Language
from melliscribe.models.vocabulary import StoresState
from melliscribe.models.vocabulary import Temperament
from melliscribe.pipeline.extraction.base import ExtractionResult
from tests.support.builders import build_output
from tests.support.builders import build_transcript
from tests.support.builders import heard
from tests.support.builders import heard_text
from tests.support.builders import mention_hive

HIVE = Hive(id=uuid.uuid4(), identifier="3", created_at=datetime.now(UTC))
TRANSCRIPT = build_transcript(
    "Ruche trois.",
    "Reine vue, couvain sur tous les stades.",
    "Elles sont calmes.",
    "Traitement acide oxalique, cinq millilitres par cadre.",
    "Penser à poser une hausse.",
)


def assemble_record(result, transcript, context):
    record = _assemble(result, transcript, context)
    assert record is not None
    return record


def _context(previous=None, language=Language.FR):
    return AssemblyContext(
        recording_id=TRANSCRIPT.recording_id,
        language=language,
        captured_on=date(2026, 5, 12),
        hives=[HIVE],
        transcription_provider="fake",
        transcription_model="fake-1",
        previous=previous,
    )


def _full_output(**overrides):
    fields = {
        "hive_mentions": [mention_hive("trois", "Ruche trois")],
        "queen_seen": heard("seen", "Reine vue", 1),
        "brood": heard("all_stages", "couvain sur tous les stades", 1),
        "temperament": heard("calm", "Elles sont calmes", 2),
        "treatments": [
            {
                "product": heard_text("acide oxalique", "acide oxalique", 3),
                "dose": heard_text(
                    "cinq millilitres par cadre", "cinq millilitres par cadre", 3
                ),
                "applied_on": None,
            }
        ],
        "actions_to_do": [
            {
                "text": "poser une hausse",
                "confidence": 0.9,
                "phrases": [{"text": "poser une hausse", "segment_index": 4}],
                "issue": None,
            }
        ],
        "detected_language": "fr",
    }
    fields.update(overrides)
    return ExtractionResult(
        output=build_output(**fields), model="claude-opus-5", prompt_version="1"
    )


def test_a_full_dictation_becomes_a_record():
    record = assemble_record(_full_output(), TRANSCRIPT, _context())
    assert record is not None
    assert record.hive_id == HIVE.id
    assert record.queen_seen.status is FieldStatus.SYSTEM_DERIVED
    assert record.stores.status is FieldStatus.UNKNOWN
    assert record.stores.value is None
    [treatment] = record.treatments
    assert treatment.product.value == "acide oxalique"
    assert treatment.dose.value == "cinq millilitres par cadre"
    [action] = record.actions_to_do
    assert action.text.value == "poser une hausse"
    assert record.confirmed_at is None
    assert record.provenance.extraction_model == "claude-opus-5"
    assert record.provenance.uncertainty_threshold > 0
    assert record.detected_language is Language.FR


def test_an_empty_dictation_produces_no_record():
    """FR-016b."""
    result = _full_output(is_inspection=False)
    assert _assemble(result, TRANSCRIPT, _context()) is None


def test_a_half_heard_treatment_is_flagged_not_matched():
    """FR-014c."""
    result = _full_output(
        treatments=[
            {
                "product": heard_text("acide", "acide oxalique", 3, confidence=0.4),
                "dose": heard_text(
                    None, "cinq millilitres par cadre", 3, issue="unmappable"
                ),
                "applied_on": None,
            }
        ]
    )
    record = assemble_record(result, TRANSCRIPT, _context())
    [treatment] = record.treatments
    assert treatment.product.status is FieldStatus.UNCERTAIN
    assert treatment.product.value is None
    assert treatment.dose.status is FieldStatus.UNCERTAIN


def test_reprocessing_preserves_confirmed_fields():
    """FR-010, FR-026c: a beekeeper's edit permanently wins."""
    first = assemble_record(_full_output(), TRANSCRIPT, _context())
    confirmed = first.model_copy(
        update={
            "temperament": ObservationField[Temperament](
                status=FieldStatus.CONFIRMED, value=Temperament.NERVOUS
            ),
            "stores": ObservationField[StoresState](
                status=FieldStatus.CONFIRMED, value=StoresState.LOW
            ),
        }
    )
    second = assemble_record(
        _full_output(temperament=heard("aggressive", "Elles sont calmes", 2)),
        TRANSCRIPT,
        _context(previous=confirmed),
    )
    assert second.id == first.id
    assert second.temperament.value is Temperament.NERVOUS
    assert second.temperament.status is FieldStatus.CONFIRMED
    assert second.stores.value is StoresState.LOW


def test_reprocessing_keeps_a_confirmed_hive():
    first = assemble_record(_full_output(hive_mentions=[]), TRANSCRIPT, _context())
    confirmed = first.model_copy(
        update={
            "hive": ObservationField[uuid.UUID](
                status=FieldStatus.CONFIRMED, value=HIVE.id
            )
        }
    )
    second = assemble_record(
        _full_output(hive_mentions=[]), TRANSCRIPT, _context(previous=confirmed)
    )
    assert second.hive_id == HIVE.id


def test_reprocessing_keeps_confirmed_actions_without_duplicating_them():
    first = assemble_record(_full_output(), TRANSCRIPT, _context())
    [action] = first.actions_to_do
    confirmed_action = action.model_copy(
        update={
            "text": ObservationField[str](
                status=FieldStatus.CONFIRMED, value="poser une hausse"
            )
        }
    )
    previous = first.model_copy(update={"actions_to_do": [confirmed_action]})
    second = assemble_record(_full_output(), TRANSCRIPT, _context(previous=previous))
    assert [a.text.status for a in second.actions_to_do] == [FieldStatus.CONFIRMED]


def test_an_unclear_hive_is_flagged_for_several_hives():
    result = _full_output(
        hive_mentions=[
            mention_hive("trois", "Ruche trois"),
            mention_hive("quatre", "Ruche trois"),
        ]
    )
    record = assemble_record(result, TRANSCRIPT, _context())
    assert record.hive.flag_reason is FlagReason.MULTIPLE_HIVES
    assert record.hive_id is None
