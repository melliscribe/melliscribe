# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The application-owned transcription interface (ADR-0001, ADR-0002).

A provider swap never reaches domain code: everything behind this protocol is
an adapter. The provider itself is chosen in ADR-0002, which is still Proposed.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from melliscribe.models.language import Language
    from melliscribe.models.transcript import TranscriptSegment


@dataclass(frozen=True)
class TranscriptionResult:
    """What a backend returns.

    Attributes:
        segments: Ordered segments with timestamps. Required: a backend that
            cannot supply segment timings fails ADR-0002 criterion 3.
        language_detected: The language the backend heard, if it reports one.
    """

    segments: list[TranscriptSegment]
    language_detected: Language | None = None


class TranscriptionBackend(Protocol):
    """Turns audio into a timestamped transcript."""

    provider: str
    model: str

    def transcribe(
        self, audio: bytes, audio_format: str, language: Language
    ) -> TranscriptionResult:
        """Transcribe one recording.

        Args:
            audio: The audio bytes.
            audio_format: The detected media type of `audio`.
            language: The account language the dictation is expected in.

        Returns:
            The segments and the detected language.
        """
        ...


class TranscriptionNotConfiguredError(RuntimeError):
    """No transcription provider is configured yet (ADR-0002 is Proposed)."""


class UnconfiguredTranscriptionBackend:
    """Fails every call with an attributable error until ADR-0002 is decided.

    The pipeline records the failure against the transcription stage and keeps
    the recording, so nothing is lost while the provider is undecided.
    """

    provider = "unconfigured"
    model = "none"

    def transcribe(
        self,
        audio: bytes,  # noqa: ARG002 - protocol signature
        audio_format: str,  # noqa: ARG002
        language: Language,  # noqa: ARG002
    ) -> TranscriptionResult:
        """Refuse to transcribe.

        Args:
            audio: Unused.
            audio_format: Unused.
            language: Unused.

        Raises:
            TranscriptionNotConfiguredError: Always.
        """
        msg = "no transcription provider configured (ADR-0002 is not decided)"
        raise TranscriptionNotConfiguredError(msg)
