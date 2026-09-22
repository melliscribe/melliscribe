# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Builders for extraction outputs and transcripts, so tests state only intent."""

from __future__ import annotations

import uuid
from typing import Any

from melliscribe.models.transcript import Transcript
from melliscribe.models.transcript import TranscriptSegment
from melliscribe.pipeline.extraction.schema import ExtractionOutput


def build_transcript(*texts: str, recording_id: uuid.UUID | None = None) -> Transcript:
    """Build a transcript with one five-second segment per text.

    Args:
        *texts: The segment texts, in order.
        recording_id: The recording id; random when omitted.

    Returns:
        The transcript.
    """
    segments = [
        TranscriptSegment(text=text, start_seconds=5.0 * i, end_seconds=5.0 * i + 4.5)
        for i, text in enumerate(texts)
    ]
    return Transcript(
        id=uuid.uuid4(),
        recording_id=recording_id or uuid.uuid4(),
        full_text=" ".join(texts),
        segments=segments,
    )


def unmentioned() -> dict[str, Any]:
    """Return an observation the dictation did not cover.

    Returns:
        The observation as a dict.
    """
    return {
        "mentioned": False,
        "value": None,
        "confidence": 0.0,
        "phrases": [],
        "issue": None,
    }


def heard(
    value: str | None,
    phrase: str,
    segment: int = 0,
    confidence: float = 0.95,
    issue: str | None = None,
) -> dict[str, Any]:
    """Return an observation that was heard.

    Args:
        value: The coded value, or None when unmappable.
        phrase: The verbatim phrase.
        segment: The segment index the phrase came from.
        confidence: The extraction confidence.
        issue: The extraction issue, if any.

    Returns:
        The observation as a dict.
    """
    return {
        "mentioned": True,
        "value": value,
        "confidence": confidence,
        "phrases": [{"text": phrase, "segment_index": segment}],
        "issue": issue,
    }


FIELD_NAMES = (
    "queen_seen",
    "brood",
    "brood_pattern",
    "stores",
    "temperament",
    "brood_frames",
    "stores_frames",
    "bee_frames",
)
COUNT_NAMES = {"brood_frames", "stores_frames", "bee_frames"}


def to_observation(name: str, heard_field: dict[str, Any]) -> dict[str, Any] | None:
    """Convert a per-field test value into a flat observation.

    Args:
        name: The field.
        heard_field: A dict from `heard`, `counted`, `unmentioned` or `uncounted`.

    Returns:
        The observation, or None when the field was not mentioned.
    """
    if not heard_field["mentioned"]:
        return None
    is_count = name in COUNT_NAMES
    return {
        "field": name,
        "value": None if is_count else heard_field["value"],
        "number": heard_field["value"] if is_count else None,
        "approximate": heard_field.get("approximate", False),
        "unit": heard_field.get("unit") if is_count else None,
        "confidence": heard_field["confidence"],
        "phrases": heard_field["phrases"],
        "issue": heard_field["issue"],
    }


def build_output(**overrides: Any) -> ExtractionOutput:
    """Build an extraction output where nothing was mentioned, then override.

    Per-field keyword arguments (`temperament=heard(...)`) become observations.

    Args:
        **overrides: Top-level fields, or per-field values, to set.

    Returns:
        The validated extraction output.
    """
    data: dict[str, Any] = {
        "is_inspection": True,
        "hive_mentions": [],
        "covers_multiple_hives": False,
        "spoken_date": None,
        "observations": [],
        "treatments": [],
        "actions_to_do": [],
        "detected_language": None,
    }
    for name in FIELD_NAMES:
        if name in overrides:
            observation = to_observation(name, overrides.pop(name))
            if observation is not None:
                data["observations"].append(observation)
    data.update(overrides)
    return ExtractionOutput.model_validate(data)


def mention_hive(identifier: str, phrase: str, segment: int = 0) -> dict[str, Any]:
    """Return a hive mention.

    Args:
        identifier: The identifier as said.
        phrase: The verbatim phrase.
        segment: The segment index.

    Returns:
        The mention as a dict.
    """
    return {
        "identifier": identifier,
        "phrase": {"text": phrase, "segment_index": segment},
    }


def heard_text(
    text: str | None, phrase: str, segment: int = 0, **kwargs: Any
) -> dict[str, Any]:
    """Return a free-text observation (treatment product or dose) that was heard.

    Args:
        text: The text as spoken, or None when unusable.
        phrase: The verbatim phrase.
        segment: The segment index.
        **kwargs: Overrides for confidence and issue.

    Returns:
        The observation as a dict.
    """
    observation = heard(text, phrase, segment, **kwargs)
    observation["text"] = observation.pop("value")
    return observation


def counted(
    value: float | None,
    phrase: str,
    segment: int = 0,
    *,
    approximate: bool = False,
    unit: str | None = "frames",
    confidence: float = 0.95,
    issue: str | None = None,
) -> dict[str, Any]:
    """Return a frame count that was heard.

    Args:
        value: The number said, or None when no number was heard.
        phrase: The verbatim phrase.
        segment: The segment index.
        approximate: Whether it was said as a range or a hedge.
        unit: What was counted, frames or faces.
        confidence: The extraction confidence.
        issue: The extraction issue, if any.

    Returns:
        The count as a dict.
    """
    return {
        "mentioned": True,
        "value": value,
        "approximate": approximate,
        "unit": unit,
        "confidence": confidence,
        "phrases": [{"text": phrase, "segment_index": segment}],
        "issue": issue,
    }


def uncounted() -> dict[str, Any]:
    """Return a frame count the dictation did not give.

    Returns:
        The count as a dict.
    """
    return {
        "mentioned": False,
        "value": None,
        "approximate": False,
        "unit": None,
        "confidence": 0.0,
        "phrases": [],
        "issue": None,
    }
