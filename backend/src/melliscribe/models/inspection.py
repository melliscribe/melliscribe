# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The inspection record and the observation field it is built from.

"Flagged rather than guessed" lives here, as validators, because a validator is
a cheaper and stronger guarantee than an eval (SC-004).
"""

from __future__ import annotations

from datetime import date
from datetime import datetime
from enum import StrEnum
from typing import Annotated
from typing import Self
from uuid import UUID

from pydantic import Field
from pydantic import model_validator

from melliscribe.models.base import Model
from melliscribe.models.language import Language
from melliscribe.models.provenance import Provenance
from melliscribe.models.vocabulary import BroodPattern
from melliscribe.models.vocabulary import BroodState
from melliscribe.models.vocabulary import QueenSeen
from melliscribe.models.vocabulary import StoresState
from melliscribe.models.vocabulary import Temperament


class FieldStatus(StrEnum):
    """How far a field's value can be trusted — the beekeeper-facing signal."""

    UNKNOWN = "unknown"
    """The dictation did not cover this. Never carries a value."""
    UNCERTAIN = "uncertain"
    """Heard, but not trusted. May carry a proposal, never a value."""
    SYSTEM_DERIVED = "system_derived"
    """Extracted with confidence, not yet confirmed by the beekeeper."""
    CONFIRMED = "confirmed"
    """Entered or confirmed by the beekeeper. Immune to later extraction."""


class FlagReason(StrEnum):
    """Why a field is `UNCERTAIN`, as a language-neutral code.

    The reason is shown to the beekeeper through the i18n catalogues under
    `flag_reason.<value>`.
    """

    LOW_CONFIDENCE = "low_confidence"
    UNMAPPABLE = "unmappable"
    UNCLEAR_CORRECTION = "unclear_correction"
    MULTIPLE_HIVES = "multiple_hives"
    NO_MATCHING_HIVE = "no_matching_hive"
    OTHER_LANGUAGE = "other_language"
    UNKNOWN_TERM = "unknown_term"
    DATE_CONFLICT = "date_conflict"
    APPROXIMATE_COUNT = "approximate_count"
    """A frame count said as a range or a hedge; never rounded (FR-006k)."""
    IMPLAUSIBLE_COUNT = "implausible_count"
    """A frame count that is negative, over the limit, or not a half step."""
    COUNT_CONTRADICTION = "count_contradiction"
    """A frame count and its state field contradict each other (FR-006l)."""


FrameCount = Annotated[float, Field(ge=0, multiple_of=0.5)]
"""A number of frames, in steps of one half (FR-006j)."""


class SegmentRef(Model):
    """A pointer to the transcript segment a phrase was spoken in (FR-023)."""

    segment_index: int
    start_seconds: float
    end_seconds: float


class ObservationField[T](Model):
    """One field of an inspection record.

    Attributes:
        status: How far the field can be trusted.
        value: The set value. None unless `SYSTEM_DERIVED` or `CONFIRMED`.
        proposal: A best guess awaiting confirmation. Only on `UNCERTAIN`, and
            never treated as set for history, export or trends (FR-006e).
        verbatim: Every phrase the field was derived from, as spoken (FR-006b).
        segment_refs: Where each phrase sits in the audio (FR-023).
        confidence: Extraction confidence. Internal: drives the status and is
            never shown to the beekeeper as a number (FR-009).
        flag_reason: Why the field is `UNCERTAIN`.
    """

    status: FieldStatus
    value: T | None = None
    proposal: T | None = None
    verbatim: list[str] = Field(default_factory=list)
    segment_refs: list[SegmentRef] = Field(default_factory=list)
    confidence: float | None = None
    flag_reason: FlagReason | None = None

    @model_validator(mode="after")
    def _check_status_invariants(self) -> Self:
        """Reject every combination the status forbids.

        Returns:
            The validated field.

        Raises:
            ValueError: When the value, proposal or reason contradicts the status.
        """
        status = self.status
        if status is FieldStatus.UNKNOWN:
            if self.value is not None or self.proposal is not None:
                msg = "an UNKNOWN field never carries a value or a proposal"
                raise ValueError(msg)
            if self.verbatim:
                msg = "an UNKNOWN field was not mentioned, so it has no verbatim"
                raise ValueError(msg)
        elif status is FieldStatus.UNCERTAIN:
            if self.value is not None:
                msg = "an UNCERTAIN field carries a proposal, never a value"
                raise ValueError(msg)
            if self.flag_reason is None:
                msg = "an UNCERTAIN field requires a flag_reason"
                raise ValueError(msg)
        elif status is FieldStatus.SYSTEM_DERIVED and self.value is None:
            msg = "a SYSTEM_DERIVED field requires a value"
            raise ValueError(msg)
        if status is not FieldStatus.UNCERTAIN and self.proposal is not None:
            msg = "only an UNCERTAIN field may carry a proposal"
            raise ValueError(msg)
        return self

    @classmethod
    def unknown(cls) -> Self:
        """Build a field the dictation did not cover.

        Returns:
            An `UNKNOWN` field.
        """
        return cls(status=FieldStatus.UNKNOWN)

    def get_set_value(self) -> T | None:
        """Return the value history, export and trends may use.

        Returns:
            The value, or None. A proposal is never returned (FR-006e).
        """
        return self.value


class Treatment(Model):
    """A product applied to the colony. Never inferred (FR-014c).

    Attributes:
        product: The product as spoken; no controlled vocabulary.
        dose: The dose as spoken; not normalised into units.
        applied_on: When it was applied, if said.
    """

    product: ObservationField[str]
    dose: ObservationField[str]
    applied_on: date | None = None


class ActionToDo(Model):
    """Something to come back and do, as phrased. Free text by design."""

    text: ObservationField[str]


class InspectionRecord(Model):
    """The structured outcome of one inspection of one hive.

    Attributes:
        id: Server-assigned identifier.
        recording_id: The recording it was derived from.
        transcript_id: The transcript it was derived from.
        language: The language extraction ran against.
        detected_language: The language the dictation was heard in, when it
            disagrees with `language` the review offers re-processing (FR-026e).
        captured_on: The day the recording was made, kept visible when a
            spoken date disagrees with it (FR-016a).
        spoken_hive_identifier: The hive identifier as said, used to create
            the hive from review when it matches none (FR-015b).
        hive: The hive; the value is a hive id, the verbatim what was said.
        inspection_date: Defaults to `captured_on`; a spoken date wins (FR-016).
        queen_seen: Whether the queen was seen.
        brood: The brood nest state.
        stores: The stores state.
        temperament: The colony's temperament.
        brood_pattern: How the brood is laid out, apart from its stages
            (FR-006m).
        brood_frames: Frames carrying brood (FR-006j).
        stores_frames: Frames of honey and pollen stores.
        bee_frames: Frames covered with bees.
        treatments: Treatments applied.
        actions_to_do: Things to come back and do.
        confirmed_at: When the beekeeper confirmed the whole record. None is a
            valid saved state (FR-024).
        provenance: What produced the record (FR-011).
    """

    id: UUID
    recording_id: UUID
    transcript_id: UUID
    language: Language
    detected_language: Language | None = None
    captured_on: date
    spoken_hive_identifier: str | None = None
    hive: ObservationField[UUID]
    inspection_date: ObservationField[date]
    queen_seen: ObservationField[QueenSeen]
    brood: ObservationField[BroodState]
    stores: ObservationField[StoresState]
    temperament: ObservationField[Temperament]
    brood_pattern: ObservationField[BroodPattern] = Field(
        default_factory=ObservationField[BroodPattern].unknown
    )
    brood_frames: ObservationField[FrameCount] = Field(
        default_factory=ObservationField[FrameCount].unknown
    )
    stores_frames: ObservationField[FrameCount] = Field(
        default_factory=ObservationField[FrameCount].unknown
    )
    bee_frames: ObservationField[FrameCount] = Field(
        default_factory=ObservationField[FrameCount].unknown
    )
    treatments: list[Treatment] = Field(default_factory=list)
    actions_to_do: list[ActionToDo] = Field(default_factory=list)
    confirmed_at: datetime | None = None
    provenance: Provenance

    @property
    def hive_id(self) -> UUID | None:
        """The resolved hive, or None while the hive field is unresolved."""
        return self.hive.value


OBSERVATION_FIELD_NAMES = (
    "queen_seen",
    "brood",
    "brood_pattern",
    "stores",
    "temperament",
)
"""The observation fields that carry a controlled vocabulary."""

COUNT_FIELD_NAMES = ("brood_frames", "stores_frames", "bee_frames")
"""The frame counts: numbers in half-frame steps, no vocabulary (FR-006j)."""

SCALAR_FIELD_NAMES = (
    "hive",
    "inspection_date",
    *OBSERVATION_FIELD_NAMES,
    *COUNT_FIELD_NAMES,
)
"""Every single-valued field of a record, in display order."""
