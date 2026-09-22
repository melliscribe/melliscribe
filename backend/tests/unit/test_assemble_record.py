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
from melliscribe.domain.inspection.corrections import confirm_record
from melliscribe.models.hive import Hive
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField
from melliscribe.models.language import Language
from melliscribe.models.vocabulary import BroodPattern
from melliscribe.models.vocabulary import BroodState
from melliscribe.models.vocabulary import StoresState
from melliscribe.models.vocabulary import Temperament
from melliscribe.pipeline.extraction.base import ExtractionResult
from tests.support.builders import build_output
from tests.support.builders import build_transcript
from tests.support.builders import counted
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


BROOD_TRANSCRIPT = build_transcript(
    "Ruche trois.",
    "Pas de couvain du tout.",
    "Du couvain sur trois cadres.",
    "Des œufs, des larves et de l'operculé, mais très en mosaïque.",
    "Cinq cadres de couvain, deux de miel, huit cadres de population.",
    "Pas de réserves.",
)


def _assemble_brood(**fields):
    return assemble_record(
        ExtractionResult(
            output=build_output(**fields), model="claude-opus-5", prompt_version="2"
        ),
        BROOD_TRANSCRIPT,
        _context(),
    )


def test_a_brood_count_above_zero_with_no_brood_flags_both():
    """FR-006l, US1/AC21: neither value is chosen over the other."""
    record = _assemble_brood(
        brood=heard("no_brood", "Pas de couvain du tout", 1),
        brood_frames=counted(3, "Du couvain sur trois cadres", 2),
    )
    for field in (record.brood, record.brood_frames):
        assert field.status is FieldStatus.UNCERTAIN
        assert field.flag_reason is FlagReason.COUNT_CONTRADICTION
        assert field.value is None
        assert field.proposal is None
    assert record.brood.verbatim == ["Pas de couvain du tout"]


def test_zero_brood_frames_with_brood_present_flags_both():
    record = _assemble_brood(
        brood=heard("all_stages", "Des œufs, des larves et de l'operculé", 3),
        brood_frames=counted(0, "Du couvain sur trois cadres", 2),
    )
    assert record.brood.flag_reason is FlagReason.COUNT_CONTRADICTION
    assert record.brood_frames.flag_reason is FlagReason.COUNT_CONTRADICTION


def test_stores_frames_with_stores_stated_as_none_flags_both():
    record = _assemble_brood(
        stores=heard("none", "Pas de réserves", 5),
        stores_frames=counted(2, "deux de miel", 4),
    )
    assert record.stores.flag_reason is FlagReason.COUNT_CONTRADICTION
    assert record.stores_frames.flag_reason is FlagReason.COUNT_CONTRADICTION


def test_consistent_counts_and_states_stand():
    record = _assemble_brood(
        brood=heard("all_stages", "Des œufs, des larves et de l'operculé", 3),
        brood_frames=counted(5, "Cinq cadres de couvain", 4),
    )
    assert record.brood.status is FieldStatus.SYSTEM_DERIVED
    assert record.brood_frames.value == 5


def test_a_confirmed_field_is_never_flagged_by_a_contradiction():
    first = _assemble_brood(brood=heard("no_brood", "Pas de couvain du tout", 1))
    confirmed = first.model_copy(
        update={
            "brood": ObservationField[BroodState](
                status=FieldStatus.CONFIRMED, value=BroodState.NO_BROOD
            )
        }
    )
    second = assemble_record(
        ExtractionResult(
            output=build_output(
                brood_frames=counted(3, "Du couvain sur trois cadres", 2)
            ),
            model="claude-opus-5",
            prompt_version="2",
        ),
        BROOD_TRANSCRIPT,
        _context(previous=confirmed),
    )
    assert second.brood.status is FieldStatus.CONFIRMED
    assert second.brood_frames.flag_reason is FlagReason.COUNT_CONTRADICTION


def test_stages_and_pattern_are_kept_apart():
    """FR-006m, US1/AC23."""
    phrase = "Des œufs, des larves et de l'operculé, mais très en mosaïque"
    record = _assemble_brood(
        brood=heard("all_stages", phrase, 3),
        brood_pattern=heard("patchy", phrase, 3),
    )
    assert record.brood.value is BroodState.ALL_STAGES
    assert record.brood_pattern.value is BroodPattern.PATCHY


def test_three_counts_in_one_breath_land_in_their_own_fields():
    """US1/AC22."""
    record = _assemble_brood(
        brood_frames=counted(5, "Cinq cadres de couvain", 4),
        stores_frames=counted(2, "deux de miel", 4),
    )
    assert record.brood_frames.value == 5
    assert record.stores_frames.value == 2
    assert record.stores_frames.verbatim == ["deux de miel"]
    assert record.bee_frames.status is FieldStatus.UNKNOWN


def test_a_record_saved_before_the_counts_existed_still_loads():
    document = assemble_record(_full_output(), TRANSCRIPT, _context()).model_dump()
    for name in ("brood_pattern", "brood_frames", "stores_frames", "bee_frames"):
        del document[name]
    record = type(
        assemble_record(_full_output(), TRANSCRIPT, _context())
    ).model_validate(document)
    assert record.bee_frames.status is FieldStatus.UNKNOWN


def test_a_clearly_stated_count_stands_after_an_unclear_correction():
    """FR-006l defers to FR-006f: a correction is not a contradiction."""
    record = _assemble_brood(
        stores=heard("none", "Pas de réserves", 5, issue="unclear_correction"),
        stores_frames=counted(2, "deux de miel", 4),
    )
    assert record.stores.flag_reason is FlagReason.UNCLEAR_CORRECTION
    assert record.stores_frames.status is FieldStatus.SYSTEM_DERIVED
    assert record.stores_frames.value == 2


def test_reprocessing_keeps_confirmation_only_if_nothing_new_is_unsettled():
    """A re-processed record with new unchecked values is no longer confirmed."""
    confirmed = assemble_record(_full_output(), TRANSCRIPT, _context()).model_copy(
        update={"confirmed_at": datetime.now(UTC)}
    )
    second = assemble_record(_full_output(), TRANSCRIPT, _context(previous=confirmed))
    assert second.confirmed_at is None


def test_reprocessing_a_fully_confirmed_record_stays_confirmed():
    first = assemble_record(_full_output(), TRANSCRIPT, _context())
    confirmed = confirm_record(first)
    second = assemble_record(_full_output(), TRANSCRIPT, _context(previous=confirmed))
    assert second.confirmed_at == confirmed.confirmed_at
