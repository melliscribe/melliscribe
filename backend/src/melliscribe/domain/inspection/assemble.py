# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Assemble an inspection record from an extraction.

Pure domain logic: no database, no API, no provider. The same function serves
first processing, re-processing after a language correction, the CLI and the
eval harness, so they cannot disagree.

Re-processing merges rather than replaces (FR-010, FR-026c): every field the
beekeeper confirmed is carried over untouched, and the record keeps its id.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from dataclasses import field
from datetime import UTC
from datetime import date
from datetime import datetime
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.inspection.corrections import has_unsettled_fields
from melliscribe.domain.inspection.counts import assign_count
from melliscribe.domain.inspection.counts import flag_contradictions
from melliscribe.domain.inspection.dates import resolve_inspection_date
from melliscribe.domain.inspection.hive_match import resolve_hive
from melliscribe.domain.inspection.status import assign_status
from melliscribe.domain.inspection.status import normalise_text
from melliscribe.models.inspection import COUNT_FIELD_NAMES
from melliscribe.models.inspection import OBSERVATION_FIELD_NAMES
from melliscribe.models.inspection import SCALAR_FIELD_NAMES
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import InspectionRecord
from melliscribe.models.provenance import Provenance
from melliscribe.models.vocabulary import VOCABULARY_VERSION
from melliscribe.pipeline.extraction.observations import read_observations
from melliscribe.pipeline.extraction.schema import EXTRACTION_SCHEMA_VERSION
from melliscribe.pipeline.extraction.schema import ExtractedCount
from melliscribe.pipeline.extraction.schema import ExtractedObservation
from melliscribe.pipeline.extraction.thresholds import UNCERTAINTY_THRESHOLD

if TYPE_CHECKING:
    from collections.abc import Sequence

    from melliscribe.models.hive import Hive
    from melliscribe.models.language import Language
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.base import ExtractionResult


@dataclass(frozen=True)
class AssemblyContext:
    """Everything assembly needs besides the extraction itself.

    Attributes:
        recording_id: The recording the record derives from.
        language: The language extraction ran against.
        captured_on: The device's local day at capture.
        hives: The beekeeper's hives, for matching.
        transcription_provider: The ASR provider, for provenance.
        transcription_model: The ASR model, for provenance.
        previous: The existing record when re-processing; its confirmed fields
            are preserved.
        now: When extraction ran.
    """

    recording_id: uuid.UUID
    language: Language
    captured_on: date
    hives: Sequence[Hive]
    transcription_provider: str
    transcription_model: str
    previous: InspectionRecord | None = None
    now: datetime = field(default_factory=lambda: datetime.now(UTC))


def assemble_record(
    result: ExtractionResult, transcript: Transcript, context: AssemblyContext
) -> InspectionRecord | None:
    """Build the record for one extraction.

    Args:
        result: The extraction and what produced it.
        transcript: The transcript it was extracted from.
        context: Recording, hives and any previous record.

    Returns:
        The record, or None when the dictation holds no inspection content
        (FR-016b).
    """
    output = result.output
    if not output.is_inspection:
        return None
    hive, spoken_hive = resolve_hive(output, transcript, context.hives)
    document: dict[str, Any] = {
        "id": context.previous.id if context.previous else uuid.uuid4(),
        "recording_id": context.recording_id,
        "transcript_id": transcript.id,
        "language": context.language,
        "detected_language": output.detected_language or transcript.language_detected,
        "captured_on": context.captured_on,
        "spoken_hive_identifier": spoken_hive,
        "hive": hive.model_dump(),
        "inspection_date": resolve_inspection_date(
            output, transcript, context.captured_on
        ).model_dump(),
        "treatments": [
            {
                "product": assign_status(t.product, transcript).model_dump(),
                "dose": assign_status(t.dose, transcript).model_dump(),
                "applied_on": t.applied_on,
            }
            for t in output.treatments
        ],
        "actions_to_do": [
            {"text": assign_status(action, transcript).model_dump()}
            for action in output.actions_to_do
        ],
        "confirmed_at": context.previous.confirmed_at if context.previous else None,
        "provenance": Provenance(
            transcription_provider=context.transcription_provider,
            transcription_model=context.transcription_model,
            extraction_model=result.model,
            prompt_version=result.prompt_version,
            vocabulary_version=VOCABULARY_VERSION,
            extraction_schema_version=EXTRACTION_SCHEMA_VERSION,
            uncertainty_threshold=UNCERTAINTY_THRESHOLD,
            extracted_at=context.now,
        ),
    }
    fields = read_observations(output)
    for name in OBSERVATION_FIELD_NAMES:
        view = fields[name]
        assert isinstance(view, ExtractedObservation)  # noqa: S101 - by construction
        document[name] = assign_status(view, transcript).model_dump()
    for name in COUNT_FIELD_NAMES:
        view = fields[name]
        assert isinstance(view, ExtractedCount)  # noqa: S101 - by construction
        document[name] = assign_count(view, transcript).model_dump()
    if context.previous is not None:
        _preserve_confirmed(document, context.previous)
    flag_contradictions(document)
    record = InspectionRecord.model_validate(document)
    if record.confirmed_at is not None and has_unsettled_fields(record):
        # New unchecked values arrived: the record needs the beekeeper again.
        record = record.model_copy(update={"confirmed_at": None})
    return record


def _preserve_confirmed(document: dict[str, Any], previous: InspectionRecord) -> None:
    """Carry every confirmed field of `previous` into `document`.

    Args:
        document: The freshly assembled record, as a dict; updated in place.
        previous: The record being re-processed.
    """
    for name in SCALAR_FIELD_NAMES:
        field_value = getattr(previous, name)
        if field_value.status is FieldStatus.CONFIRMED:
            document[name] = field_value.model_dump()
            if name == "hive":
                document["spoken_hive_identifier"] = previous.spoken_hive_identifier
    kept_treatments = [
        t.model_dump()
        for t in previous.treatments
        if FieldStatus.CONFIRMED in {t.product.status, t.dose.status}
    ]
    if kept_treatments:
        kept_products = {
            normalise_text(str(t["product"]["value"] or "")) for t in kept_treatments
        }
        document["treatments"] = kept_treatments + [
            t
            for t in document["treatments"]
            if normalise_text(
                str(t["product"]["value"] or t["product"]["proposal"] or "")
            )
            not in kept_products
        ]
    kept_actions = [
        a.model_dump()
        for a in previous.actions_to_do
        if a.text.status is FieldStatus.CONFIRMED
    ]
    if kept_actions:
        kept_texts = {
            normalise_text(str(a["text"]["value"] or "")) for a in kept_actions
        }
        document["actions_to_do"] = kept_actions + [
            a
            for a in document["actions_to_do"]
            if normalise_text(str(a["text"]["value"] or a["text"]["proposal"] or ""))
            not in kept_texts
        ]
