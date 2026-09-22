# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Field status assignment: where "flagged rather than guessed" is decided.

The extractor says what it heard. This module decides what the beekeeper is
told to trust, with rules that are versioned with the threshold rather than
left to a prompt:

- not mentioned: `UNKNOWN`, null value, whatever the extractor returned
  alongside (FR-007, SC-004);
- mentioned but mapping to no value: `UNCERTAIN`, verbatim kept (FR-006d);
- an extraction issue — unclear correction, other language, unknown term:
  `UNCERTAIN` with that reason (FR-006f, FR-026f, FR-014b);
- below the threshold, or a quote that cannot be found in the transcript:
  `UNCERTAIN`, the value demoted to a proposal (FR-008, FR-006e);
- otherwise `SYSTEM_DERIVED`.
"""

from __future__ import annotations

import re
import unicodedata
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField
from melliscribe.models.inspection import SegmentRef
from melliscribe.pipeline.extraction.schema import ExtractedAction
from melliscribe.pipeline.extraction.schema import ExtractedObservation
from melliscribe.pipeline.extraction.schema import ExtractedText
from melliscribe.pipeline.extraction.schema import ExtractionIssue
from melliscribe.pipeline.extraction.thresholds import UNCERTAINTY_THRESHOLD

if TYPE_CHECKING:
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import Phrase

_ISSUE_REASONS = {
    ExtractionIssue.UNMAPPABLE: FlagReason.UNMAPPABLE,
    ExtractionIssue.UNCLEAR_CORRECTION: FlagReason.UNCLEAR_CORRECTION,
    ExtractionIssue.OTHER_LANGUAGE: FlagReason.OTHER_LANGUAGE,
    ExtractionIssue.UNKNOWN_TERM: FlagReason.UNKNOWN_TERM,
}


def normalise_text(text: str) -> str:
    """Normalise text for quote matching: case, accents, spacing, punctuation.

    Args:
        text: The text to normalise.

    Returns:
        The normalised text.
    """
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(c for c in decomposed if not unicodedata.combining(c))
    words = re.sub(r"[^\w]+", " ", stripped)
    return " ".join(words.split())


def resolve_phrases(
    phrases: list[Phrase], transcript: Transcript
) -> tuple[list[str], list[SegmentRef], bool]:
    """Resolve extracted phrases against the transcript.

    Args:
        phrases: The phrases the extractor quoted.
        transcript: The transcript they should come from.

    Returns:
        The verbatim texts, the segment references that resolved, and whether
        every phrase is actually present in the transcript.
    """
    haystack = normalise_text(transcript.full_text)
    verbatim: list[str] = []
    refs: list[SegmentRef] = []
    all_found = bool(phrases)
    for phrase in phrases:
        verbatim.append(phrase.text)
        if 0 <= phrase.segment_index < len(transcript.segments):
            segment = transcript.segments[phrase.segment_index]
            refs.append(
                SegmentRef(
                    segment_index=phrase.segment_index,
                    start_seconds=segment.start_seconds,
                    end_seconds=segment.end_seconds,
                )
            )
        needle = normalise_text(phrase.text)
        if not needle or needle not in haystack:
            all_found = False
    return verbatim, refs, all_found


type Heard = ExtractedObservation[Any] | ExtractedText | ExtractedAction
"""Every extracted shape that becomes one observation field."""


def assign_status(observation: Heard, transcript: Transcript) -> ObservationField[Any]:
    """Turn an extracted observation into a field with a trustworthy status.

    Args:
        observation: What the extractor heard.
        transcript: The transcript it was extracted from.

    Returns:
        The observation field, to be validated into its typed record field.
    """
    if isinstance(observation, ExtractedObservation):
        mentioned, value = observation.mentioned, observation.value
    elif isinstance(observation, ExtractedText):
        mentioned, value = observation.mentioned, observation.text
    else:
        mentioned, value = True, observation.text
    if not mentioned:
        return ObservationField[Any](status=FieldStatus.UNKNOWN)
    verbatim, refs, quoted = resolve_phrases(observation.phrases, transcript)
    confidence = observation.confidence
    reason: FlagReason | None = None
    if observation.issue is not None:
        reason = _ISSUE_REASONS[observation.issue]
    elif value is None:
        reason = FlagReason.UNMAPPABLE
    elif confidence < UNCERTAINTY_THRESHOLD or not quoted:
        reason = FlagReason.LOW_CONFIDENCE
    if reason is None:
        return ObservationField[Any](
            status=FieldStatus.SYSTEM_DERIVED,
            value=value,
            verbatim=verbatim,
            segment_refs=refs,
            confidence=confidence,
        )
    return ObservationField[Any](
        status=FieldStatus.UNCERTAIN,
        proposal=value,
        verbatim=verbatim,
        segment_refs=refs,
        confidence=confidence,
        flag_reason=reason,
    )
