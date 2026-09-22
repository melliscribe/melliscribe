# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Fake pipeline stages, so API and pipeline tests never call a provider."""

from __future__ import annotations

from typing import TYPE_CHECKING

from melliscribe.models.transcript import TranscriptSegment
from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.extraction.base import ExtractionResult
from melliscribe.pipeline.transcription.base import TranscriptionResult
from tests.support.builders import build_output

if TYPE_CHECKING:
    from datetime import date

    from melliscribe.models.language import Language
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import ExtractionOutput


class FakeTranscriber:
    """Returns one segment per line of the audio bytes, decoded as UTF-8."""

    provider = "fake"
    model = "fake-asr-1"

    def __init__(self) -> None:
        self.calls: list[Language] = []
        self.fail_with: Exception | None = None
        self.language_detected: Language | None = None

    def transcribe(
        self, audio: bytes, audio_format: str, language: Language
    ) -> TranscriptionResult:
        """Split the "audio" into segments.

        Args:
            audio: UTF-8 text standing in for audio.
            audio_format: Ignored.
            language: Recorded for assertions.

        Returns:
            The segments.

        Raises:
            Exception: `fail_with`, when set.
        """
        del audio_format
        self.calls.append(language)
        if self.fail_with is not None:
            raise self.fail_with
        lines = [line for line in audio.decode().splitlines() if line.strip()]
        return TranscriptionResult(
            segments=[
                TranscriptSegment(
                    text=line, start_seconds=5.0 * i, end_seconds=5.0 * i + 4
                )
                for i, line in enumerate(lines)
            ],
            language_detected=self.language_detected,
        )


class FakeExtractor:
    """Returns a scripted extraction output."""

    def __init__(self) -> None:
        self.output: ExtractionOutput = build_output()
        self.fail_with: Exception | None = None
        self.calls: list[tuple[Transcript, Language]] = []

    def extract(
        self, transcript: Transcript, language: Language, captured_on: date
    ) -> ExtractionResult:
        """Return the scripted output.

        Args:
            transcript: Recorded for assertions.
            language: Recorded for assertions.
            captured_on: Ignored.

        Returns:
            The scripted output.

        Raises:
            ExtractionFailedError: `fail_with`, when set.
        """
        del captured_on
        self.calls.append((transcript, language))
        if self.fail_with is not None:
            raise self.fail_with
        return ExtractionResult(
            output=self.output, model="fake-llm", prompt_version="1"
        )


__all__ = ["ExtractionFailedError", "FakeExtractor", "FakeTranscriber"]


class FakeBatchExtractor:
    """Answers a batch in reverse order, optionally leaving some unanswered."""

    def __init__(self, extractor: FakeExtractor) -> None:
        self.extractor = extractor
        self.batches: list[list[str]] = []
        self.unanswered: set[str] = set()
        self.errors: dict[str, Exception] = {}

    def extract_many(self, items):
        """Return results keyed by custom id, in reverse submission order.

        Args:
            items: The batch items.

        Returns:
            Results by custom id; unanswered ids are absent.
        """
        self.batches.append([item.custom_id for item in items])
        results = {}
        for item in reversed(items):
            if item.custom_id in self.unanswered:
                continue
            if item.custom_id in self.errors:
                results[item.custom_id] = self.errors[item.custom_id]
                continue
            results[item.custom_id] = self.extractor.extract(
                item.transcript, item.language, item.captured_on
            )
        return results
