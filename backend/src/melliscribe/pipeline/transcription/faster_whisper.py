# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Self-hosted Whisper through `faster-whisper` — ADR-0002's first candidate.

**Provisional.** ADR-0002 is still Proposed: this adapter exists so a dictation
produces a record end to end while the bilingual spike measures it against the
other candidates. It is selected with `MELLISCRIBE_ASR_PROVIDER=faster-whisper`
and installed with the optional `asr-local` extra.

Why it is the first candidate (ADR-0002 criteria):

- segment timestamps come back with every segment (criterion 3);
- the glossary steers recognition as hotwords, applied to every 30-second
  window, within Whisper's token budget (criterion 2);
- audio never leaves the server, so nothing new needs disclosing (criterion 4).

French accuracy — criterion 1, the one that decides — is exactly what the spike
measures; small models are known to be weaker there.
"""

from __future__ import annotations

import io
import math
import threading
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.vocabulary.glossary import GLOSSARY
from melliscribe.domain.vocabulary.glossary import TermCategory
from melliscribe.models.language import Language
from melliscribe.models.transcript import TranscriptSegment
from melliscribe.pipeline.transcription.base import TranscriptionResult

if TYPE_CHECKING:
    from collections.abc import Callable

PROVIDER = "faster-whisper"
DEFAULT_MODEL = "small"
HOTWORD_TOKEN_BUDGET = 200
"""faster-whisper keeps at most 223 hotword tokens, cutting from the end; the
most useful terms come first and the list stops inside this budget."""
DETECTION_CONFIDENCE = 0.8
"""Below this, a detected language is not reported: on noise or silence the
detector still names a language, and a false mismatch warning (FR-026e) would
send the beekeeper re-processing a recording that was fine."""
_OPENING = {
    Language.FR: "Visite de ruche.",
    Language.EN: "Hive inspection.",
}
_CATEGORY_ORDER = (
    TermCategory.COLONY,
    TermCategory.CONDITION,
    TermCategory.EQUIPMENT,
    TermCategory.TREATMENT,
    TermCategory.ACTIVITY,
)


def _estimate_tokens(text: str) -> int:
    """Estimate Whisper tokens when no tokenizer is at hand (tests).

    Args:
        text: The text.

    Returns:
        A deliberately pessimistic estimate: two tokens per word.
    """
    return 2 * len(text.split())


def build_hotwords(
    language: Language, count_tokens: Callable[[str], int] = _estimate_tokens
) -> str:
    """Build the glossary hotwords that steer every window of a dictation.

    Hotwords, unlike an initial prompt, are applied to each 30-second window,
    so a term said at 1:30 is steered as much as one said at 0:05.

    Args:
        language: The dictation language.
        count_tokens: Counts Whisper tokens; the model's own tokenizer in use.

    Returns:
        A short opening and glossary terms in that language, colony and
        condition terms first, within the token budget.
    """
    terms: list[str] = []
    for category in _CATEGORY_ORDER:
        for term in GLOSSARY:
            if term.category is category:
                form = term.fr if language is Language.FR else term.en
                terms.extend(part.strip() for part in form.split("/"))
    text = _OPENING[language]
    for term in dict.fromkeys(terms):
        candidate = f"{text} {term},"
        if count_tokens(candidate) > HOTWORD_TOKEN_BUDGET:
            break
        text = candidate
    return text.rstrip(",")


def _decode(data: bytes) -> Any:  # noqa: ANN401 - a numpy array
    """Decode any container ffmpeg understands into 16 kHz mono samples.

    Args:
        data: The audio file's bytes.

    Returns:
        The samples.
    """
    from faster_whisper import decode_audio  # noqa: PLC0415 - optional extra

    return decode_audio(io.BytesIO(data))


class FasterWhisperBackend:
    """A [TranscriptionBackend][melliscribe.pipeline.transcription.base.TranscriptionBackend] running Whisper locally."""  # noqa: E501

    provider = PROVIDER

    def __init__(
        self,
        model_size: str = DEFAULT_MODEL,
        *,
        model: Any = None,  # noqa: ANN401 - a faster_whisper.WhisperModel
        decode: Callable[[bytes], Any] = _decode,
    ) -> None:
        self.model = model_size
        self._model = model
        self._decode = decode
        self._lock = threading.Lock()

    def _get_model(self) -> Any:  # noqa: ANN401 - a faster_whisper.WhisperModel
        """Load the model on first use; loading takes seconds and memory.

        Returns:
            The Whisper model.
        """
        if self._model is None:
            from faster_whisper import WhisperModel  # noqa: PLC0415 - optional extra

            self._model = WhisperModel(self.model, device="cpu", compute_type="int8")
        return self._model

    def _count_tokens(self, model: Any, text: str) -> int:  # noqa: ANN401
        """Count Whisper tokens with the model's tokenizer when it has one.

        Args:
            model: The Whisper model.
            text: The text.

        Returns:
            The token count.
        """
        tokenizer = getattr(model, "hf_tokenizer", None)
        if tokenizer is None:
            return _estimate_tokens(text)
        return len(tokenizer.encode(" " + text).ids)

    def transcribe(
        self,
        audio: bytes,
        audio_format: str,  # noqa: ARG002 - ffmpeg detects the container itself
        language: Language,
    ) -> TranscriptionResult:
        """Transcribe in the account language, reporting what was detected.

        Args:
            audio: The audio bytes.
            audio_format: Unused; the container is detected from the bytes.
            language: The account language, which transcription always uses.

        Returns:
            Timestamped segments, and the detected language when it is one of
            the supported two.
        """
        # One transcription at a time: loading the model twice would double its
        # memory, and parallel CPU decoding would starve everything else.
        with self._lock:
            model = self._get_model()
            samples = self._decode(audio)
            detected, probability, _ = model.detect_language(audio=samples)
            segments, _ = model.transcribe(
                samples,
                language=language.value,
                hotwords=build_hotwords(
                    language, lambda text: self._count_tokens(model, text)
                ),
                vad_filter=True,
                condition_on_previous_text=False,
            )
            heard = list(segments)
        result: list[TranscriptSegment] = []
        for segment in heard:
            text = segment.text.strip()
            if not text:
                continue
            start = max(segment.start, result[-1].end_seconds if result else 0.0)
            result.append(
                TranscriptSegment(
                    text=text,
                    start_seconds=start,
                    end_seconds=max(start, segment.end),
                    confidence=math.exp(segment.avg_logprob),
                )
            )
        supported = {lang.value for lang in Language}
        return TranscriptionResult(
            segments=result,
            language_detected=Language(detected)
            if detected in supported and probability >= DETECTION_CONFIDENCE
            else None,
        )
