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


def build_output(**overrides: Any) -> ExtractionOutput:
    """Build an extraction output where nothing was mentioned, then override.

    Args:
        **overrides: Top-level fields to replace.

    Returns:
        The validated extraction output.
    """
    data: dict[str, Any] = {
        "is_inspection": True,
        "hive_mentions": [],
        "covers_multiple_hives": False,
        "spoken_date": None,
        "queen_seen": unmentioned(),
        "brood": unmentioned(),
        "stores": unmentioned(),
        "temperament": unmentioned(),
        "treatments": [],
        "actions_to_do": [],
        "detected_language": None,
    }
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
