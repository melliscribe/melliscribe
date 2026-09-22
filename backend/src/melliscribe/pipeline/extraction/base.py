# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The application-owned extraction interface (ADR-0001, ADR-0003).

An extractor turns a transcript into the schema-constrained
[ExtractionOutput][melliscribe.pipeline.extraction.schema.ExtractionOutput].
Turning that output into an
[InspectionRecord][melliscribe.models.inspection.InspectionRecord] — statuses,
thresholds, hive matching, dates, confirmed-field merging — is domain logic in
`melliscribe.domain.inspection`, so it is the same whichever provider extracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from datetime import date

    from melliscribe.models.language import Language
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import ExtractionOutput


@dataclass(frozen=True)
class ExtractionResult:
    """What an extractor returns.

    Attributes:
        output: The schema-valid extraction.
        model: The model that actually served the call.
        prompt_version: The prompt version used.
    """

    output: ExtractionOutput
    model: str
    prompt_version: str


class Extractor(Protocol):
    """Turns a transcript into a structured extraction."""

    def extract(
        self, transcript: Transcript, language: Language, captured_on: date
    ) -> ExtractionResult:
        """Extract one transcript.

        Args:
            transcript: The transcript to read.
            language: The account language to extract against (FR-026f).
            captured_on: The capture day, to resolve relative spoken dates.

        Returns:
            The extraction and what produced it.
        """
        ...


class ExtractionFailedError(RuntimeError):
    """The extraction call did not produce a usable record."""


@dataclass(frozen=True)
class BatchItem:
    """One transcript in a batch.

    Attributes:
        custom_id: The recording's client-generated id, as a string. Results
            are keyed by it, never by position (D4).
        transcript: The transcript.
        language: The account language.
        captured_on: The capture day.
    """

    custom_id: str
    transcript: Transcript
    language: Language
    captured_on: date


class BatchExtractor(Protocol):
    """Extracts many transcripts at once, at lower cost and higher latency."""

    def extract_many(
        self, items: list[BatchItem]
    ) -> dict[str, ExtractionResult | Exception]:
        """Extract a batch.

        Args:
            items: The transcripts to extract.

        Returns:
            A result or an error per custom id. Items missing from the mapping
            did not finish in time and must be extracted another way.
        """
        ...
