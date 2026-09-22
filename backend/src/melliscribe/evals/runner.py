# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The eval runner: one entry point per pipeline stage (ADR-0005).

Extraction cases run through the same
[assemble_record][melliscribe.domain.inspection.assemble.assemble_record] the
API uses, so the eval measures what a beekeeper would actually see — statuses
included — not the raw model output.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from datetime import UTC
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.inspection.assemble import AssemblyContext
from melliscribe.domain.inspection.assemble import assemble_record
from melliscribe.evals.scoring import CaseOutcome
from melliscribe.evals.scoring import compute_word_error_rate
from melliscribe.evals.scoring import find_glossary_hits
from melliscribe.evals.scoring import score_case
from melliscribe.evals.scoring import summarise_extraction
from melliscribe.models.hive import Hive
from melliscribe.models.inspection import OBSERVATION_FIELD_NAMES
from melliscribe.models.inspection import ObservationField
from melliscribe.models.transcript import Transcript

if TYPE_CHECKING:
    from collections.abc import Sequence

    from melliscribe.evals.dataset import ExtractionCase
    from melliscribe.evals.dataset import TranscriptionCase
    from melliscribe.models.inspection import InspectionRecord
    from melliscribe.pipeline.extraction.base import Extractor
    from melliscribe.pipeline.transcription.base import TranscriptionBackend

_HIVE_NAMESPACE = uuid.UUID("0b5c3a52-7d8e-4f0e-9a3b-2c1d6e8f9a10")


def get_private_storage() -> Path:
    """Return where private eval material lives (Principle III).

    Returns:
        `MELLISCRIBE_EVAL_STORAGE`, which must never be inside the repository.
    """
    return Path(os.environ.get("MELLISCRIBE_EVAL_STORAGE", "~/.melliscribe/evals"))


def load_transcript(case: ExtractionCase, storage: Path) -> Transcript:
    """Load a case's transcript, inline or from private storage.

    Args:
        case: The case.
        storage: The private storage root.

    Returns:
        The transcript.
    """
    recording_id = uuid.uuid5(_HIVE_NAMESPACE, case.id)
    if case.segments is not None:
        return Transcript(
            id=uuid.uuid5(recording_id, "transcript"),
            recording_id=recording_id,
            full_text=" ".join(s.text for s in case.segments),
            segments=case.segments,
        )
    path = storage.expanduser() / str(case.transcript_ref)
    data = json.loads(path.read_text("utf-8"))
    return Transcript.model_validate(data | {"recording_id": str(recording_id)})


def _collect_fields(
    record: InspectionRecord, hives: Sequence[Hive]
) -> dict[str, ObservationField[Any]]:
    """Gather a record's scorable fields, with the hive as its identifier.

    Args:
        record: The produced record.
        hives: The case's hives.

    Returns:
        The fields by name.
    """
    names = {hive.id: hive.identifier for hive in hives}
    hive = record.hive
    fields: dict[str, ObservationField[Any]] = {
        "hive": ObservationField[Any].model_validate(
            hive.model_dump() | {"value": names.get(hive.value) if hive.value else None}
        ),
        "inspection_date": ObservationField[Any].model_validate(
            record.inspection_date.model_dump(mode="json")
        ),
    }
    for name in OBSERVATION_FIELD_NAMES:
        fields[name] = getattr(record, name)
    return fields


def run_extraction_case(
    case: ExtractionCase, extractor: Extractor, storage: Path
) -> CaseOutcome:
    """Run and score one extraction case.

    Args:
        case: The case.
        extractor: The extractor under test.
        storage: The private storage root.

    Returns:
        The case outcome; an extraction error scores every field wrong.
    """
    transcript = load_transcript(case, storage)
    hives = [
        Hive(
            id=uuid.uuid5(_HIVE_NAMESPACE, identifier),
            identifier=identifier,
            created_at=datetime.now(UTC),
        )
        for identifier in case.hives
    ]
    try:
        result = extractor.extract(transcript, case.language, case.captured_on)
    except Exception as error:  # noqa: BLE001 - every failure is scored, not raised
        outcome = score_case(case, None)
        outcome.is_inspection_correct = False
        outcome.error = str(error) or type(error).__name__
        return outcome
    record = assemble_record(
        result,
        transcript,
        AssemblyContext(
            recording_id=transcript.recording_id,
            language=case.language,
            captured_on=case.captured_on,
            hives=hives,
            transcription_provider="eval",
            transcription_model="reference-transcript",
        ),
    )
    fields = _collect_fields(record, hives) if record is not None else None
    return score_case(case, fields)


def run_extraction(
    cases: Sequence[ExtractionCase], extractor: Extractor, storage: Path
) -> dict[str, Any]:
    """Run the extraction stage over a dataset.

    Args:
        cases: The extraction cases.
        extractor: The extractor under test.
        storage: The private storage root.

    Returns:
        The report: summary and per-case outcomes, JSON-serialisable.
    """
    outcomes = [run_extraction_case(case, extractor, storage) for case in cases]
    return {
        "stage": "extraction",
        "summary": asdict(summarise_extraction(outcomes)),
        "outcomes": [asdict(o) for o in outcomes],
    }


def run_transcription(
    cases: Sequence[TranscriptionCase], backend: TranscriptionBackend, storage: Path
) -> dict[str, Any]:
    """Run the transcription stage over a dataset.

    Args:
        cases: The transcription cases.
        backend: The backend under test.
        storage: The private storage root holding the audio.

    Returns:
        The report: WER and glossary recall per language, per-case detail.
    """
    per_case: list[dict[str, Any]] = []
    errors: dict[str, list[float]] = {}
    hits: dict[str, list[bool]] = {}
    for case in cases:
        audio = (storage.expanduser() / case.audio_ref).read_bytes()
        result = backend.transcribe(audio, case.audio_format, case.language)
        text = " ".join(s.text for s in result.segments)
        wer = compute_word_error_rate(case.reference_text, text)
        glossary = find_glossary_hits(case.glossary_terms, text)
        errors.setdefault(case.language.value, []).append(wer)
        hits.setdefault(case.language.value, []).extend(glossary.values())
        per_case.append(
            {
                "case_id": case.id,
                "wer": wer,
                "missed_terms": [t for t, ok in glossary.items() if not ok],
                "has_timestamps": bool(result.segments),
            }
        )
    return {
        "stage": "transcription",
        "summary": {
            "wer": {k: round(sum(v) / len(v), 2) for k, v in errors.items()},
            "glossary_recall": {
                k: round(100 * sum(v) / len(v), 2) if v else 100.0
                for k, v in hits.items()
            },
        },
        "outcomes": per_case,
    }
