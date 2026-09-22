# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read the flat observation list back into one view per field.

The schema cannot restrict a value to its field's vocabulary any more (see
`schema.py`), so this is where that guarantee lives now. Every gap is closed on
the safe side:

- a field with no observation is unmentioned — it becomes `UNKNOWN`, never a
  default (SC-004);
- a value outside the field's vocabulary, or a count without a number, is
  heard but unmappable — flagged, never forced to the nearest value (FR-006d);
- repeated observations of one field keep every phrase (FR-006b); if they
  disagree, the field is flagged rather than resolved to either (FR-006f).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from melliscribe.models.inspection import COUNT_FIELD_NAMES
from melliscribe.models.inspection import OBSERVATION_FIELD_NAMES
from melliscribe.models.vocabulary import VOCABULARIES
from melliscribe.pipeline.extraction.schema import ExtractedCount
from melliscribe.pipeline.extraction.schema import ExtractedObservation
from melliscribe.pipeline.extraction.schema import ExtractionIssue

if TYPE_CHECKING:
    from melliscribe.pipeline.extraction.schema import ExtractionOutput
    from melliscribe.pipeline.extraction.schema import Observation

type FieldView = ExtractedObservation[Any] | ExtractedCount


def _merge(name: str, repeats: list[Observation]) -> FieldView:
    """Merge every observation of one field into its per-field view.

    Args:
        name: The field.
        repeats: Its observations, in order; at least one.

    Returns:
        The field as the domain rules read it.
    """
    is_count = name in COUNT_FIELD_NAMES
    phrases = [phrase for obs in repeats for phrase in obs.phrases]
    confidence = min(obs.confidence for obs in repeats)
    issue = next((obs.issue for obs in repeats if obs.issue is not None), None)
    if is_count:
        heard = {obs.number for obs in repeats}
        value = repeats[0].number
    else:
        allowed = {v.value for v in VOCABULARIES[name].values}
        heard = {obs.value for obs in repeats}
        value = repeats[0].value if repeats[0].value in allowed else None
        if repeats[0].value is not None and value is None and issue is None:
            issue = ExtractionIssue.UNMAPPABLE
    if len(heard) > 1:
        value, issue = None, ExtractionIssue.UNCLEAR_CORRECTION
    elif value is None and issue is None:
        issue = ExtractionIssue.UNMAPPABLE
    if is_count:
        return ExtractedCount(
            mentioned=True,
            value=value,
            approximate=any(obs.approximate for obs in repeats),
            unit=repeats[0].unit,
            confidence=confidence,
            phrases=phrases,
            issue=issue,
        )
    return ExtractedObservation[Any](
        mentioned=True,
        value=value,
        confidence=confidence,
        phrases=phrases,
        issue=issue,
    )


def read_observations(output: ExtractionOutput) -> dict[str, FieldView]:
    """Return one view per field, for every field of the record.

    Args:
        output: The extraction output.

    Returns:
        Each vocabulary field and frame count, keyed by name.
    """
    grouped: dict[str, list[Observation]] = {}
    for observation in output.observations:
        grouped.setdefault(observation.field.value, []).append(observation)
    views: dict[str, FieldView] = {}
    for name in OBSERVATION_FIELD_NAMES:
        repeats = grouped.get(name)
        views[name] = (
            _merge(name, repeats)
            if repeats
            else ExtractedObservation[Any](
                mentioned=False, value=None, confidence=0.0, phrases=[], issue=None
            )
        )
    for name in COUNT_FIELD_NAMES:
        repeats = grouped.get(name)
        views[name] = (
            _merge(name, repeats)
            if repeats
            else ExtractedCount(
                mentioned=False,
                value=None,
                approximate=False,
                unit=None,
                confidence=0.0,
                phrases=[],
                issue=None,
            )
        )
    return views
