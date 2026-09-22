# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Claude extractor's request shape, parsing and tracing, without the network."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from melliscribe.models.language import Language
from melliscribe.models.trace import TraceOutcome
from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.extraction.claude import MODEL
from melliscribe.pipeline.extraction.claude import ClaudeExtractor
from melliscribe.pipeline.extraction.claude import build_request_params
from melliscribe.pipeline.extraction.schema import build_output_schema
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from tests.support.builders import build_output
from tests.support.builders import build_transcript

TRANSCRIPT = build_transcript("Ruche trois.", "Elles sont calmes.")
CAPTURED_ON = date(2026, 4, 3)


class _FakeMessages:
    def __init__(self, message):
        self._message = message
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if isinstance(self._message, Exception):
            raise self._message
        return self._message


def _client(message):
    messages = _FakeMessages(message)
    return SimpleNamespace(beta=SimpleNamespace(messages=messages)), messages


def _message(text=None, stop_reason="end_turn", model=MODEL, iterations=None):
    content = [] if text is None else [SimpleNamespace(type="text", text=text)]
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=None,
        content=content,
        model=model,
        usage=SimpleNamespace(
            input_tokens=120,
            output_tokens=400,
            cache_read_input_tokens=3000,
            cache_creation_input_tokens=0,
            iterations=iterations,
        ),
    )


def test_the_transcript_comes_after_the_cache_breakpoint():
    """D5: nothing volatile before the breakpoint."""
    params = build_request_params(TRANSCRIPT, Language.FR, CAPTURED_ON)
    [system] = params["system"]
    assert system["cache_control"] == {"type": "ephemeral"}
    assert "Elles sont calmes" not in system["text"]
    assert "2026-04-03" not in system["text"]
    assert "Elles sont calmes" in params["messages"][0]["content"]


def test_the_system_prompt_is_byte_identical_across_requests():
    first = build_request_params(TRANSCRIPT, Language.FR, CAPTURED_ON)
    other = build_transcript("Hive B2.", "Calm.")
    second = build_request_params(other, Language.EN, date(2026, 6, 1))
    assert first["system"] == second["system"]


def test_the_output_schema_is_generated_from_the_model():
    params = build_request_params(TRANSCRIPT, Language.FR, CAPTURED_ON)
    assert params["output_config"]["format"]["schema"] == build_output_schema()
    assert params["model"] == "claude-opus-5"
    assert params["thinking"] == {"type": "adaptive"}


def test_no_cache_drops_the_breakpoint():
    params = build_request_params(TRANSCRIPT, Language.FR, CAPTURED_ON, use_cache=False)
    assert "cache_control" not in params["system"][0]


def test_a_successful_extraction_is_parsed_and_traced():
    sink = InMemoryTraceSink()
    client, messages = _client(_message(build_output().model_dump_json()))
    extractor = ClaudeExtractor(sink, client=client)
    result = extractor.extract(TRANSCRIPT, Language.FR, CAPTURED_ON)
    assert result.output == build_output()
    assert result.model == MODEL
    assert messages.calls[0]["fallbacks"] == "default"
    [trace] = sink.traces
    assert trace.outcome is TraceOutcome.SUCCESS
    assert trace.cache_read_tokens == 3000
    assert trace.recording_id == TRANSCRIPT.recording_id
    assert not trace.fallback_taken


def test_a_fallback_is_traced_with_the_serving_model():
    sink = InMemoryTraceSink()
    message = _message(
        build_output().model_dump_json(),
        model="claude-opus-4-8",
        iterations=[
            SimpleNamespace(type="message"),
            SimpleNamespace(type="fallback_message"),
        ],
    )
    client, _ = _client(message)
    result = ClaudeExtractor(sink, client=client).extract(
        TRANSCRIPT, Language.FR, CAPTURED_ON
    )
    assert result.model == "claude-opus-4-8"
    assert sink.traces[0].fallback_taken


@pytest.mark.parametrize("stop_reason", ["refusal", "max_tokens"])
def test_an_unusable_response_fails_and_is_traced(stop_reason):
    sink = InMemoryTraceSink()
    client, _ = _client(_message(None, stop_reason=stop_reason))
    with pytest.raises(ExtractionFailedError):
        ClaudeExtractor(sink, client=client).extract(
            TRANSCRIPT, Language.FR, CAPTURED_ON
        )
    assert sink.traces[0].outcome is TraceOutcome.ERROR


def test_output_that_does_not_validate_is_not_repaired():
    sink = InMemoryTraceSink()
    client, _ = _client(_message('{"is_inspection": true}'))
    with pytest.raises(ExtractionFailedError, match="schema"):
        ClaudeExtractor(sink, client=client).extract(
            TRANSCRIPT, Language.FR, CAPTURED_ON
        )
