# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Human-readable rendering shared by the CLI commands (maintainer-facing)."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from melliscribe.models.inspection import OBSERVATION_FIELD_NAMES

if TYPE_CHECKING:
    from melliscribe.models.inspection import InspectionRecord
    from melliscribe.models.inspection import ObservationField
    from melliscribe.models.transcript import Transcript


def format_field(name: str, field: ObservationField[Any]) -> str:
    """Format one field as a single line.

    Args:
        name: The field name.
        field: The field.

    Returns:
        `name: status value (reason) — "verbatim" [segments]`.
    """
    value = field.value if field.value is not None else field.proposal
    parts = [f"{name}: {field.status.value}"]
    if value is not None:
        parts.append(str(getattr(value, "value", value)))
        if field.proposal is not None:
            parts[-1] += " (proposed)"
    if field.flag_reason is not None:
        parts.append(f"[{field.flag_reason.value}]")
    if field.verbatim:
        parts.append("— " + " / ".join(f'"{v}"' for v in field.verbatim))
    if field.segment_refs:
        parts.append("@ " + ",".join(str(r.segment_index) for r in field.segment_refs))
    return " ".join(parts)


def format_record(record: InspectionRecord) -> str:
    """Format a record, one field per line.

    Args:
        record: The record.

    Returns:
        The rendered record.
    """
    lines = [
        format_field("hive", record.hive),
        format_field("inspection_date", record.inspection_date),
    ]
    lines.extend(format_field(n, getattr(record, n)) for n in OBSERVATION_FIELD_NAMES)
    for i, treatment in enumerate(record.treatments):
        lines.append(format_field(f"treatment[{i}].product", treatment.product))
        lines.append(format_field(f"treatment[{i}].dose", treatment.dose))
    lines.extend(
        format_field(f"action[{i}]", action.text)
        for i, action in enumerate(record.actions_to_do)
    )
    provenance = record.provenance
    lines.append(
        f"provenance: {provenance.extraction_model} prompt v{provenance.prompt_version}"
        f" vocabulary v{provenance.vocabulary_version}"
        f" threshold {provenance.uncertainty_threshold}"
    )
    return "\n".join(lines)


def format_transcript(transcript: Transcript) -> str:
    """Format a transcript with segment timings.

    Args:
        transcript: The transcript.

    Returns:
        One `[index] start-end text` line per segment.
    """
    return "\n".join(
        f"[{i}] {s.start_seconds:7.2f}-{s.end_seconds:7.2f} {s.text}"
        for i, s in enumerate(transcript.segments)
    )
