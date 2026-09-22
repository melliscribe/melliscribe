# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Frame counts (FR-006j, FR-006k, FR-006l).

A count is taken only from what was said. Faces are converted to frames here,
not by the model, so the conversion is tested and the phrase keeps the words
actually spoken. Anything doubtful is flagged, and an approximate or implausible
count carries no suggested number: any suggestion would be a rounding.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.inspection.status import ISSUE_REASONS
from melliscribe.domain.inspection.status import resolve_phrases
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField
from melliscribe.models.vocabulary import BroodState
from melliscribe.models.vocabulary import StoresState
from melliscribe.pipeline.extraction.schema import CountUnit
from melliscribe.pipeline.extraction.thresholds import UNCERTAINTY_THRESHOLD

if TYPE_CHECKING:
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import ExtractedCount

FRAME_COUNT_LIMIT = 40
"""Above this, a count is a mishearing until the beekeeper says otherwise.

Hive equipment is out of scope, so one generous limit covers two brood boxes
and several supers while still catching a misheard order of magnitude."""

_BROOD_PRESENT = {
    BroodState.ALL_STAGES,
    BroodState.NO_EGGS,
    BroodState.DRONE_BROOD_ONLY,
}
_STORES_PRESENT = {StoresState.PLENTIFUL, StoresState.ADEQUATE, StoresState.LOW}


def assign_count(
    count: ExtractedCount, transcript: Transcript
) -> ObservationField[Any]:
    """Turn an extracted count into a field with a trustworthy status.

    Args:
        count: What the extractor heard.
        transcript: The transcript it was extracted from.

    Returns:
        The count field, in frames.
    """
    if not count.mentioned:
        return ObservationField[Any](status=FieldStatus.UNKNOWN)
    verbatim, refs, quoted = resolve_phrases(count.phrases, transcript)
    frames = _to_frames(count)
    reason: FlagReason | None = None
    proposal: float | None = None
    if count.issue is not None:
        reason = ISSUE_REASONS[count.issue]
    elif count.value is None:
        reason = FlagReason.UNMAPPABLE
    elif count.approximate:
        reason = FlagReason.APPROXIMATE_COUNT
    elif frames is None:
        reason = FlagReason.IMPLAUSIBLE_COUNT
    elif count.confidence < UNCERTAINTY_THRESHOLD or not quoted:
        reason, proposal = FlagReason.LOW_CONFIDENCE, frames
    if reason is None:
        return ObservationField[Any](
            status=FieldStatus.SYSTEM_DERIVED,
            value=frames,
            verbatim=verbatim,
            segment_refs=refs,
            confidence=count.confidence,
        )
    return ObservationField[Any](
        status=FieldStatus.UNCERTAIN,
        proposal=proposal,
        verbatim=verbatim,
        segment_refs=refs,
        confidence=count.confidence,
        flag_reason=reason,
    )


def _to_frames(count: ExtractedCount) -> float | None:
    """Convert a spoken count to frames, refusing an implausible one.

    Args:
        count: The count as spoken.

    Returns:
        The count in frames; None when negative, above the limit, or not a
        multiple of one half.
    """
    if count.value is None:
        return None
    frames = count.value / 2 if count.unit is CountUnit.FACES else count.value
    if frames < 0 or frames > FRAME_COUNT_LIMIT or (frames * 2) % 1:
        return None
    return frames


def _contradicts(count: Any, state: Any, present: set[Any], absent: Any) -> bool:  # noqa: ANN401
    """Tell whether a count and a state contradict each other.

    Args:
        count: The frame count heard.
        state: The state heard.
        present: The states that mean something is there.
        absent: The state that means nothing is there.

    Returns:
        True for a count above zero with nothing there, or zero with
        something there.
    """
    if count is None or state is None:
        return False
    return (count > 0 and state == absent) or (count == 0 and state in present)


def flag_contradictions(document: dict[str, Any]) -> None:
    """Flag counts that contradict their state fields, both sides (FR-006l).

    Neither value is preferred, so neither keeps a value or a proposal; the
    phrases stay visible. A confirmed field is never touched — only its
    unconfirmed counterpart is flagged.

    Args:
        document: The assembled record, as a dict; updated in place.
    """
    pairs = (
        ("brood_frames", "brood", _BROOD_PRESENT, BroodState.NO_BROOD),
        ("stores_frames", "stores", _STORES_PRESENT, StoresState.NONE),
    )
    for count_name, state_name, present, absent in pairs:
        count, state = document[count_name], document[state_name]
        count_value = (
            count["value"] if count["value"] is not None else count["proposal"]
        )
        state_value = (
            state["value"] if state["value"] is not None else state["proposal"]
        )
        if not _contradicts(count_value, state_value, present, absent):
            continue
        for field in (count, state):
            if field["status"] is FieldStatus.CONFIRMED:
                continue
            field.update(
                status=FieldStatus.UNCERTAIN,
                value=None,
                proposal=None,
                flag_reason=FlagReason.COUNT_CONTRADICTION,
            )
