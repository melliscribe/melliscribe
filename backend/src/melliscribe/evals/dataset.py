# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Dataset manifests: JSONL, one case per line (ADR-0005).

The manifest is versioned; the audio is not. A case points at private storage
by reference, and every case carries a consent reference or a purpose-made
marker so the dataset's provenance can be audited (FR-027f). Synthetic cases —
transcripts written for the purpose, containing no real inspection — may hold
their segments inline, because they are not user content (Principle III).
"""

from __future__ import annotations

import json
from datetime import date
from typing import TYPE_CHECKING
from typing import Annotated
from typing import Literal
from typing import Self

from pydantic import Field
from pydantic import TypeAdapter
from pydantic import model_validator

from melliscribe.models.base import Model
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.language import Language
from melliscribe.models.transcript import TranscriptSegment

if TYPE_CHECKING:
    from pathlib import Path


class _Provenanced(Model):
    """A case whose provenance is auditable (FR-027f)."""

    id: str
    language: Language
    pair_id: str | None = None
    """Cases sharing a pair id are the same inspection in each language."""
    consent_ref: str | None = None
    """The recording's consent record, for material from a beekeeper."""
    purpose_made: bool = False
    """Recorded or written for evaluation; no beekeeper's data."""

    @model_validator(mode="after")
    def _check_provenance(self) -> Self:
        """Require a consent reference or a purpose-made marker.

        Returns:
            The validated case.

        Raises:
            ValueError: When the case has neither.
        """
        if not self.purpose_made and not self.consent_ref:
            msg = "a case needs a consent_ref or purpose_made: true (FR-027f)"
            raise ValueError(msg)
        return self


class ExpectedField(Model):
    """The reference outcome for one field."""

    status: FieldStatus
    value: str | None = None
    """The coded value, hive identifier or ISO date; omitted when irrelevant."""


class ExpectedRecord(Model):
    """The reference outcome for one dictation."""

    is_inspection: bool = True
    fields: dict[str, ExpectedField] = Field(default_factory=dict)


class ExtractionCase(_Provenanced):
    """An extraction case: a transcript and the record it should produce."""

    stage: Literal["extraction"]
    captured_on: date
    hives: list[str] = Field(default_factory=list)
    segments: list[TranscriptSegment] | None = None
    """Inline segments, for synthetic purpose-made transcripts only."""
    transcript_ref: str | None = None
    """A transcript JSON file in private storage."""
    expected: ExpectedRecord

    @model_validator(mode="after")
    def _check_source(self) -> Self:
        """Require exactly one transcript source.

        Returns:
            The validated case.

        Raises:
            ValueError: When the case has no transcript or two.
        """
        if (self.segments is None) == (self.transcript_ref is None):
            msg = "an extraction case needs exactly one of segments or transcript_ref"
            raise ValueError(msg)
        return self


class TranscriptionCase(_Provenanced):
    """A transcription case: audio in private storage and its reference text."""

    stage: Literal["transcription"]
    audio_ref: str
    audio_format: str
    reference_text: str
    glossary_terms: list[str] = Field(default_factory=list)
    """Glossary terms spoken in the audio, in the case's language."""


Case = Annotated[ExtractionCase | TranscriptionCase, Field(discriminator="stage")]
_CASE_ADAPTER: TypeAdapter[ExtractionCase | TranscriptionCase] = TypeAdapter(Case)


def load_manifest(path: Path) -> list[ExtractionCase | TranscriptionCase]:
    """Load and validate every case of a manifest.

    Args:
        path: The JSONL manifest.

    Returns:
        The cases, in file order.
    """
    return [
        _CASE_ADAPTER.validate_python(json.loads(line))
        for line in path.read_text("utf-8").splitlines()
        if line.strip()
    ]
