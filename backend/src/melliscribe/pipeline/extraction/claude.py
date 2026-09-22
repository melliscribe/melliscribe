# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Extraction with Claude and structured outputs (ADR-0003).

The response is schema-valid by construction: there is no JSON-repair path, no
prose-stripping and no retry-on-parse-failure. If one of those ever appears
here, the contract is being worked around rather than used.

Prompt layout is load-bearing (D5): the stable system prompt — instructions,
vocabularies, glossary, few-shot examples — carries the cache breakpoint, and
everything that varies per request goes after it, in the user turn.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

import anthropic
from pydantic import ValidationError

from melliscribe.models.recording import PipelineStage
from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.extraction.base import ExtractionResult
from melliscribe.pipeline.extraction.prompts import CURRENT_PROMPT_VERSION
from melliscribe.pipeline.extraction.prompts import render_system_prompt
from melliscribe.pipeline.extraction.schema import ExtractionOutput
from melliscribe.pipeline.extraction.schema import build_output_schema
from melliscribe.pipeline.tracing.writer import CallUsage
from melliscribe.pipeline.tracing.writer import trace_call

if TYPE_CHECKING:
    from datetime import date

    from melliscribe.models.language import Language
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.tracing.writer import TraceSink

MODEL = "claude-opus-5"
"""Not downgraded on a hunch: a cheaper tier is an eval-backed decision."""
MAX_TOKENS = 16000
FALLBACK_BETA = "server-side-fallback-2026-07-01"
"""Server-side refusal fallback; Claude API only, not the Batches API."""
PROVIDER = "anthropic"


def render_user_turn(
    transcript: Transcript, language: Language, captured_on: date
) -> str:
    """Render the per-request part of the prompt: everything after the cache.

    Args:
        transcript: The transcript to extract.
        language: The account language.
        captured_on: The capture day.

    Returns:
        The user message text.
    """
    return (
        f"Account language: {language.value}\n"
        f"Capture date: {captured_on.isoformat()}\n\n"
        f"Transcript:\n{transcript.render_numbered()}"
    )


def build_request_params(
    transcript: Transcript,
    language: Language,
    captured_on: date,
    *,
    prompt_version: str = CURRENT_PROMPT_VERSION,
    use_cache: bool = True,
) -> dict[str, Any]:
    """Build the Messages API parameters, shared by live and batch extraction.

    Args:
        transcript: The transcript to extract.
        language: The account language.
        captured_on: The capture day.
        prompt_version: The prompt version to render.
        use_cache: Whether to place the cache breakpoint.

    Returns:
        The request parameters.
    """
    system_block: dict[str, Any] = {
        "type": "text",
        "text": render_system_prompt(prompt_version),
    }
    if use_cache:
        system_block["cache_control"] = {"type": "ephemeral"}
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": [system_block],
        "messages": [
            {
                "role": "user",
                "content": render_user_turn(transcript, language, captured_on),
            }
        ],
        "thinking": {"type": "adaptive"},
        "output_config": {
            "format": {"type": "json_schema", "schema": build_output_schema()}
        },
    }


def parse_output(message: Any) -> ExtractionOutput:  # noqa: ANN401 - SDK message types
    """Read the structured output from a response.

    Args:
        message: The Messages API response.

    Returns:
        The validated extraction.

    Raises:
        ExtractionFailedError: When the model refused, ran out of tokens, or
            the output does not validate — never repaired.
    """
    if message.stop_reason == "refusal":
        category = getattr(message.stop_details, "category", None)
        msg = f"extraction refused (category: {category})"
        raise ExtractionFailedError(msg)
    if message.stop_reason == "max_tokens":
        msg = "extraction hit max_tokens before completing"
        raise ExtractionFailedError(msg)
    text = next((b.text for b in message.content if b.type == "text"), None)
    if text is None:
        msg = "extraction returned no output"
        raise ExtractionFailedError(msg)
    try:
        return ExtractionOutput.model_validate_json(text)
    except ValidationError as error:
        msg = f"extraction output does not match the schema: {error}"
        raise ExtractionFailedError(msg) from error


class ClaudeExtractor:
    """The Claude-backed [Extractor][melliscribe.pipeline.extraction.base.Extractor]."""

    def __init__(
        self,
        trace_sink: TraceSink,
        *,
        client: anthropic.Anthropic | None = None,
        prompt_version: str = CURRENT_PROMPT_VERSION,
        use_cache: bool = True,
    ) -> None:
        self._client = client or anthropic.Anthropic()
        self._trace_sink = trace_sink
        self.prompt_version = prompt_version
        self._use_cache = use_cache

    def extract(
        self, transcript: Transcript, language: Language, captured_on: date
    ) -> ExtractionResult:
        """Extract one transcript, tracing the call whatever its outcome.

        Args:
            transcript: The transcript to read.
            language: The account language.
            captured_on: The capture day.

        Returns:
            The extraction and the model that actually served it.
        """
        params = build_request_params(
            transcript,
            language,
            captured_on,
            prompt_version=self.prompt_version,
            use_cache=self._use_cache,
        )
        with trace_call(
            self._trace_sink,
            recording_id=transcript.recording_id,
            stage=PipelineStage.EXTRACTION,
            provider=PROVIDER,
            model=MODEL,
            prompt_version=self.prompt_version,
        ) as call:
            message = self._client.beta.messages.create(
                **params, betas=[FALLBACK_BETA], fallbacks="default"
            )
            usage = message.usage
            call.model = message.model
            call.usage = CallUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_input_tokens,
                cache_write_tokens=usage.cache_creation_input_tokens,
            )
            call.fallback_taken = any(
                getattr(iteration, "type", None) == "fallback_message"
                for iteration in (getattr(usage, "iterations", None) or [])
            )
            output = parse_output(message)
        return ExtractionResult(
            output=output, model=message.model, prompt_version=self.prompt_version
        )
