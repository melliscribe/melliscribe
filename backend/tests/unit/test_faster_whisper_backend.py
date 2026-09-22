# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The self-hosted Whisper adapter, against a fake model (ADR-0002 candidate)."""

from __future__ import annotations

import math
from types import SimpleNamespace

import pytest

from melliscribe.models.language import Language
from melliscribe.pipeline.transcription.factory import build_transcription_backend
from melliscribe.pipeline.transcription.faster_whisper import HOTWORD_TOKEN_BUDGET
from melliscribe.pipeline.transcription.faster_whisper import FasterWhisperBackend
from melliscribe.pipeline.transcription.faster_whisper import build_hotwords


class _FakeModel:
    def __init__(self, segments, detected="fr", probability=0.97):
        self.segments = segments
        self.detected = detected
        self.probability = probability
        self.calls = []

    def detect_language(self, audio=None, **kwargs):
        return self.detected, self.probability, [(self.detected, self.probability)]

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        return iter(self.segments), SimpleNamespace(language=kwargs["language"])


def _segment(text, start, end, avg_logprob=-0.1):
    return SimpleNamespace(text=text, start=start, end=end, avg_logprob=avg_logprob)


def _backend(model):
    return FasterWhisperBackend(
        model_size="small", model=model, decode=lambda data: data
    )


def test_segments_keep_their_timestamps_and_are_trimmed():
    model = _FakeModel(
        [_segment(" Ruche trois.", 0.0, 1.5), _segment(" Calmes.", 1.5, 3.0)]
    )
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.FR)
    assert [s.text for s in result.segments] == ["Ruche trois.", "Calmes."]
    assert result.segments[1].start_seconds == 1.5
    assert result.segments[0].confidence == pytest.approx(math.exp(-0.1))


def test_transcription_runs_in_the_account_language_with_the_glossary():
    model = _FakeModel([_segment("x", 0, 1)])
    _backend(model).transcribe(b"audio", "audio/webm", Language.FR)
    [call] = model.calls
    assert call["language"] == "fr"
    assert "couvain" in call["hotwords"]
    assert "initial_prompt" not in call
    assert call["vad_filter"] is True


def test_the_detected_language_is_reported_not_obeyed():
    """FR-026e: a disagreement is surfaced; transcription keeps the setting."""
    model = _FakeModel([_segment("Hive three.", 0, 1)], detected="en")
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.FR)
    assert model.calls[0]["language"] == "fr"
    assert result.language_detected is Language.EN


def test_an_unsupported_detected_language_is_not_reported():
    model = _FakeModel([_segment("x", 0, 1)], detected="de")
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.FR)
    assert result.language_detected is None


def test_an_unsure_detection_is_not_reported():
    """On noise the detector still names a language; that is not a finding."""
    model = _FakeModel([_segment("x", 0, 1)], detected="en", probability=0.4)
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.FR)
    assert result.language_detected is None


def test_overlapping_segments_are_made_contiguous():
    model = _FakeModel([_segment("a", 0.0, 2.0), _segment("b", 1.8, 3.0)])
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.EN)
    assert result.segments[1].start_seconds == 2.0


def test_empty_segments_are_dropped():
    model = _FakeModel([_segment("  ", 0.0, 1.0), _segment("Calm.", 1.0, 2.0)])
    result = _backend(model).transcribe(b"audio", "audio/webm", Language.EN)
    assert [s.text for s in result.segments] == ["Calm."]


def test_hotwords_use_the_language_forms():
    french = build_hotwords(Language.FR)
    assert "couvain" in french
    assert "brood" not in french
    assert "brood" in build_hotwords(Language.EN)


def test_hotwords_stay_inside_the_token_budget_keeping_the_first_terms():
    """Whisper cuts hotwords from the end; the colony terms must survive."""

    def count(text):
        return len(text)  # one token per character: a harsh tokenizer

    french = build_hotwords(Language.FR, count)
    assert count(french) <= HOTWORD_TOKEN_BUDGET
    assert french.startswith("Visite de ruche. reine")


def test_the_real_tokenizer_budget_holds_when_the_model_is_cached():
    """Measured with Whisper's tokenizer, when a model is available locally."""
    pytest.importorskip("faster_whisper")
    from faster_whisper.utils import download_model

    try:
        path = download_model("tiny", local_files_only=True)
    except Exception:  # noqa: BLE001 - no cached model: nothing to measure
        pytest.skip("no cached Whisper model")
    from tokenizers import Tokenizer

    tokenizer = Tokenizer.from_file(f"{path}/tokenizer.json")

    def count(text):
        return len(tokenizer.encode(" " + text).ids)

    for language in Language:
        assert count(build_hotwords(language, count)) <= HOTWORD_TOKEN_BUDGET


def test_the_factory_selects_it(monkeypatch):
    monkeypatch.setenv("MELLISCRIBE_ASR_PROVIDER", "faster-whisper")
    monkeypatch.setenv("MELLISCRIBE_ASR_MODEL", "tiny")
    backend = build_transcription_backend()
    assert backend.provider == "faster-whisper"
    assert backend.model == "tiny"
