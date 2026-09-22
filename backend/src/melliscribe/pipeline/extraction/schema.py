# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The extraction output model: the LLM contract (ADR-0003).

The JSON Schema Claude is constrained to is **generated** from
[ExtractionOutput][melliscribe.pipeline.extraction.schema.ExtractionOutput] by
[build_output_schema][melliscribe.pipeline.extraction.schema.build_output_schema]
— never hand-written, or the single-source-of-truth chain breaks at its most
important link.

This model says what was heard. It does not decide statuses: the uncertainty
threshold, hive matching and date rules live in `melliscribe.domain.inspection`
so they are versioned, tested and identical whichever model extracts.

Every field is required (nullable where absence is meaningful) so the model has
to take a position on each one rather than silently omitting it.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any

from anthropic import transform_schema
from pydantic import Field

from melliscribe.models.base import Model
from melliscribe.models.language import Language
from melliscribe.models.vocabulary import BroodState
from melliscribe.models.vocabulary import QueenSeen
from melliscribe.models.vocabulary import StoresState
from melliscribe.models.vocabulary import Temperament

EXTRACTION_SCHEMA_VERSION = "1"
"""Bumped on any change to this module; recorded in every record's provenance."""


class ExtractionIssue(StrEnum):
    """A reason the extractor could not assert a field with confidence."""

    UNMAPPABLE = "unmappable"
    """Heard, but fits no value of the field's vocabulary (FR-006d)."""
    UNCLEAR_CORRECTION = "unclear_correction"
    """The speaker corrected themselves and the correction is unclear (FR-006f)."""
    OTHER_LANGUAGE = "other_language"
    """The source phrase was spoken in the other supported language (FR-026f)."""
    UNKNOWN_TERM = "unknown_term"
    """The observation hinges on a word absent from the glossary (FR-014b)."""


class Phrase(Model):
    """A verbatim quote from the transcript and the segment it came from."""

    text: str = Field(
        description="Quoted exactly from the transcript, never paraphrased."
    )
    segment_index: int = Field(
        description="The [index] of the segment it was spoken in."
    )


class ExtractedObservation[T](Model):
    """What was heard about one controlled-vocabulary field."""

    mentioned: bool = Field(
        description="False when the dictation never addresses this field at all."
    )
    value: T | None = Field(
        description=(
            "The vocabulary value the speaker's words mean. Null when not "
            "mentioned, or when the words fit no value — never the nearest value."
        )
    )
    confidence: float = Field(
        description="From 0 to 1: how sure you are that value is what was meant."
    )
    phrases: list[Phrase] = Field(
        description=(
            "Every phrase this field was derived from. Empty when not mentioned."
        )
    )
    issue: ExtractionIssue | None = Field(
        description="Why the field cannot be asserted confidently, if it cannot."
    )


class ExtractedText(Model):
    """A free-text field kept as spoken: a treatment product or dose."""

    mentioned: bool
    text: str | None = Field(
        description="As spoken. Never corrected to a known product."
    )
    confidence: float = Field(description="From 0 to 1: how clearly it was heard.")
    phrases: list[Phrase]
    issue: ExtractionIssue | None


class ExtractedTreatment(Model):
    """A treatment the speaker says was applied. Never inferred (FR-014c)."""

    product: ExtractedText
    dose: ExtractedText
    applied_on: date | None = Field(
        description="Only when the speaker states when it was applied."
    )


class ExtractedAction(Model):
    """Something the speaker decided to come back and do."""

    text: str = Field(description="As phrased by the speaker, in their language.")
    confidence: float
    phrases: list[Phrase]
    issue: ExtractionIssue | None


class HiveMention(Model):
    """A hive identifier the speaker said."""

    identifier: str = Field(
        description=(
            "The identifier as said, without the word for hive: 'ruche trois' "
            "gives 'trois', 'hive B2' gives 'B2'."
        )
    )
    phrase: Phrase


class SpokenDate(Model):
    """A date the speaker gave for the inspection."""

    value: date = Field(description="Resolved against the capture date when relative.")
    phrase: Phrase


class ExtractionOutput(Model):
    """Everything extraction heard in one dictation."""

    is_inspection: bool = Field(
        description=(
            "False when the transcript is intelligible but contains no "
            "inspection content at all."
        )
    )
    hive_mentions: list[HiveMention] = Field(
        description="Every hive identifier said, in order, including repeats."
    )
    covers_multiple_hives: bool = Field(
        description="True when the dictation describes more than one hive."
    )
    spoken_date: SpokenDate | None
    queen_seen: ExtractedObservation[QueenSeen]
    brood: ExtractedObservation[BroodState]
    stores: ExtractedObservation[StoresState]
    temperament: ExtractedObservation[Temperament]
    treatments: list[ExtractedTreatment]
    actions_to_do: list[ExtractedAction]
    detected_language: Language | None = Field(
        description="The language most of the dictation is spoken in."
    )


def build_output_schema() -> dict[str, Any]:
    """Generate the JSON Schema passed as `output_config.format`.

    Returns:
        The schema, transformed by the SDK into the subset structured outputs
        accept (unsupported constraints move into descriptions).
    """
    return transform_schema(ExtractionOutput)
