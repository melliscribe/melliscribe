# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The inspection date (FR-016, FR-016a)."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from melliscribe.domain.inspection.status import resolve_phrases
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField

if TYPE_CHECKING:
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import ExtractionOutput

MAX_DAYS_FROM_CAPTURE = 1
"""A spoken date further than this from the capture day is flagged."""


def resolve_inspection_date(
    output: ExtractionOutput, transcript: Transcript, captured_on: date
) -> ObservationField[date]:
    """Resolve the inspection date.

    Defaults to the capture day; a spoken date wins when it is within a day of
    it, and is flagged — never silently accepted — when it is further away.
    The capture day stays on the record so both remain visible.

    Args:
        output: The extraction output.
        transcript: The transcript it came from.
        captured_on: The device's local day at capture.

    Returns:
        The inspection date field.
    """
    spoken = output.spoken_date
    if spoken is None:
        return ObservationField[date](
            status=FieldStatus.SYSTEM_DERIVED, value=captured_on
        )
    verbatim, refs, _ = resolve_phrases([spoken.phrase], transcript)
    if abs((spoken.value - captured_on).days) > MAX_DAYS_FROM_CAPTURE:
        return ObservationField[date](
            status=FieldStatus.UNCERTAIN,
            proposal=spoken.value,
            verbatim=verbatim,
            segment_refs=refs,
            flag_reason=FlagReason.DATE_CONFLICT,
        )
    return ObservationField[date](
        status=FieldStatus.SYSTEM_DERIVED,
        value=spoken.value,
        verbatim=verbatim,
        segment_refs=refs,
    )
