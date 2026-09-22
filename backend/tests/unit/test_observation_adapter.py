# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Schema v3: the flat observation list, read back field by field.

The flat list keeps the structured-output grammar small enough to compile; the
price is that the schema no longer constrains values per field. These tests pin
how that freedom is closed off again in code — never in the model's favour.
"""

from __future__ import annotations

from melliscribe.pipeline.extraction.observations import read_observations
from melliscribe.pipeline.extraction.schema import ExtractedCount
from melliscribe.pipeline.extraction.schema import ExtractionIssue
from melliscribe.pipeline.extraction.schema import ExtractionOutput
from tests.support.builders import build_output
from tests.support.builders import counted
from tests.support.builders import heard


def _with(*observations):
    data = build_output().model_dump()
    data["observations"] = list(observations)
    return ExtractionOutput.model_validate(data)


def _obs(field, value=None, number=None, phrase="x", **extra):
    return {
        "field": field,
        "value": value,
        "number": number,
        "approximate": extra.get("approximate", False),
        "unit": extra.get("unit"),
        "confidence": extra.get("confidence", 0.9),
        "phrases": [{"text": phrase, "segment_index": 0}],
        "issue": extra.get("issue"),
    }


def test_a_field_with_no_observation_is_unmentioned():
    fields = read_observations(build_output())
    assert not fields["temperament"].mentioned
    assert not fields["brood_frames"].mentioned


def test_a_vocabulary_value_is_read_into_its_field():
    fields = read_observations(build_output(temperament=heard("calm", "calmes", 1)))
    assert fields["temperament"].mentioned
    assert fields["temperament"].value == "calm"
    assert fields["temperament"].phrases[0].text == "calmes"


def test_a_count_is_read_from_the_number():
    fields = read_observations(
        build_output(brood_frames=counted(5, "cinq cadres", 1, unit="faces"))
    )
    count = fields["brood_frames"]
    assert isinstance(count, ExtractedCount)
    assert count.value == 5
    assert count.unit == "faces"


def test_a_value_outside_the_vocabulary_is_unmappable_never_forced():
    """FR-006d, SC-004: the schema no longer stops it, so the adapter does."""
    fields = read_observations(_with(_obs("temperament", value="grumpy")))
    temperament = fields["temperament"]
    assert temperament.mentioned
    assert temperament.value is None
    assert temperament.issue is ExtractionIssue.UNMAPPABLE
    assert temperament.phrases[0].text == "x"


def test_a_count_field_without_a_number_is_unmappable():
    fields = read_observations(_with(_obs("stores_frames", value="deux")))
    assert fields["stores_frames"].value is None
    assert fields["stores_frames"].issue is ExtractionIssue.UNMAPPABLE


def test_repeated_agreeing_observations_merge_their_phrases():
    """FR-006b: every contributing phrase is kept."""
    fields = read_observations(
        _with(
            _obs("temperament", value="nervous", phrase="nerveuses", confidence=0.9),
            _obs("temperament", value="nervous", phrase="courent", confidence=0.7),
        )
    )
    temperament = fields["temperament"]
    assert temperament.value == "nervous"
    assert [p.text for p in temperament.phrases] == ["nerveuses", "courent"]
    assert temperament.confidence == 0.7


def test_repeated_disagreeing_observations_are_flagged_not_resolved():
    fields = read_observations(
        _with(
            _obs("temperament", value="calm", phrase="calmes"),
            _obs("temperament", value="defensive", phrase="piquent"),
        )
    )
    temperament = fields["temperament"]
    assert temperament.value is None
    assert temperament.issue is ExtractionIssue.UNCLEAR_CORRECTION
    assert [p.text for p in temperament.phrases] == ["calmes", "piquent"]


def test_an_issue_on_any_repeat_is_kept():
    fields = read_observations(
        _with(
            _obs("stores", value="low", phrase="peu"),
            _obs("stores", value="low", phrase="bof", issue="other_language"),
        )
    )
    assert fields["stores"].issue is ExtractionIssue.OTHER_LANGUAGE
