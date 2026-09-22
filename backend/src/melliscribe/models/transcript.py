# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""What was said, linked back into the audio (FR-012, FR-023)."""

from __future__ import annotations

from typing import Self
from uuid import UUID

from pydantic import model_validator

from melliscribe.models.base import Model
from melliscribe.models.language import Language


class TranscriptSegment(Model):
    """One timed passage of a transcript."""

    text: str
    start_seconds: float
    end_seconds: float
    confidence: float | None = None

    @model_validator(mode="after")
    def _check_bounds(self) -> Self:
        """Reject a segment that ends before it starts.

        Returns:
            The validated segment.

        Raises:
            ValueError: When the segment's bounds are inverted.
        """
        if self.end_seconds < self.start_seconds:
            msg = "a segment cannot end before it starts"
            raise ValueError(msg)
        return self


class Transcript(Model):
    """A full transcript. Outlives the audio (FR-027c).

    Attributes:
        id: Transcript identifier.
        recording_id: The recording it transcribes.
        full_text: The whole transcript.
        segments: Ordered, non-overlapping timed segments.
        language_detected: What the ASR detected; informational only, the
            account setting governs (FR-026e).
    """

    id: UUID
    recording_id: UUID
    full_text: str
    segments: list[TranscriptSegment]
    language_detected: Language | None = None

    @model_validator(mode="after")
    def _check_segments(self) -> Self:
        """Reject segments that are out of order or overlap.

        Returns:
            The validated transcript.

        Raises:
            ValueError: When two segments overlap or are out of order.
        """
        for previous, current in zip(self.segments, self.segments[1:], strict=False):
            if current.start_seconds < previous.end_seconds:
                msg = "transcript segments must be ordered and non-overlapping"
                raise ValueError(msg)
        return self

    def render_numbered(self) -> str:
        """Render the segments one per line, prefixed by their index.

        Returns:
            The transcript as `[index] text` lines, as extraction sees it.
        """
        return "\n".join(f"[{i}] {s.text}" for i, s in enumerate(self.segments))
