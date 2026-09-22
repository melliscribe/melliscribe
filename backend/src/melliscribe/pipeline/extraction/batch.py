# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Deferred extraction through the Message Batches API, at 50% cost (D4).

The request is the live request unchanged — same prompt, schema and cached
prefix — without the server-side refusal fallback, which the Batches API
rejects. Results arrive in arbitrary order and are keyed by `custom_id`, the
recording's client-generated id.

**Deadline.** Most batches finish well inside an hour, but SC-007 promises a
record within 5 minutes of connectivity returning. A batch still running at the
deadline is cancelled, and whatever it did not finish is left out of the result
for the caller to extract live — a fallback the trace records.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

import anthropic

from melliscribe.models.recording import PipelineStage
from melliscribe.pipeline.extraction.base import ExtractionFailedError
from melliscribe.pipeline.extraction.base import ExtractionResult
from melliscribe.pipeline.extraction.claude import MODEL
from melliscribe.pipeline.extraction.claude import PROVIDER
from melliscribe.pipeline.extraction.claude import build_request_params
from melliscribe.pipeline.extraction.claude import parse_output
from melliscribe.pipeline.extraction.prompts import CURRENT_PROMPT_VERSION
from melliscribe.pipeline.tracing.writer import CallUsage
from melliscribe.pipeline.tracing.writer import trace_call

if TYPE_CHECKING:
    import uuid
    from collections.abc import Callable

    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming

    from melliscribe.pipeline.extraction.base import BatchItem
    from melliscribe.pipeline.tracing.writer import TraceSink

DEADLINE_SECONDS = 240.0
"""Leaves a minute of SC-007's five for live extraction of what is left."""
POLL_SECONDS = 10.0


class ClaudeBatchExtractor:
    """The Claude-backed batch extractor.

    Implements [BatchExtractor][melliscribe.pipeline.extraction.base.BatchExtractor].
    """

    def __init__(  # noqa: PLR0913 - clock and sleep are injected for tests
        self,
        trace_sink: TraceSink,
        *,
        client: anthropic.Anthropic | None = None,
        deadline_seconds: float = DEADLINE_SECONDS,
        poll_seconds: float = POLL_SECONDS,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._client = client or anthropic.Anthropic()
        self._trace_sink = trace_sink
        self._deadline = deadline_seconds
        self._poll = poll_seconds
        self._sleep = sleep
        self._clock = clock

    def extract_many(
        self, items: list[BatchItem]
    ) -> dict[str, ExtractionResult | Exception]:
        """Submit, wait up to the deadline, and collect what finished.

        Args:
            items: The transcripts to extract.

        Returns:
            A result or an error per custom id; unfinished ids are absent.
        """
        by_id = {item.custom_id: item for item in items}
        batch = self._client.messages.batches.create(
            requests=[
                {
                    "custom_id": item.custom_id,
                    "params": cast(
                        "MessageCreateParamsNonStreaming",
                        build_request_params(
                            item.transcript, item.language, item.captured_on
                        ),
                    ),
                }
                for item in items
            ]
        )
        started = self._clock()
        while batch.processing_status != "ended":
            if self._clock() - started >= self._deadline:
                batch = self._client.messages.batches.cancel(batch.id)
                break
            self._sleep(self._poll)
            batch = self._client.messages.batches.retrieve(batch.id)
        while batch.processing_status != "ended":
            self._sleep(1.0)
            batch = self._client.messages.batches.retrieve(batch.id)
        elapsed_ms = round((self._clock() - started) * 1000)
        results: dict[str, ExtractionResult | Exception] = {}
        for entry in self._client.messages.batches.results(batch.id):
            item = by_id.get(entry.custom_id)
            if item is None:
                continue
            outcome = self._collect(
                item.transcript.recording_id, entry.result, elapsed_ms
            )
            if outcome is not None:
                results[entry.custom_id] = outcome
        return results

    def _collect(
        self,
        recording_id: uuid.UUID,
        result: Any,  # noqa: ANN401 - the SDK's result union
        elapsed_ms: int,
    ) -> ExtractionResult | Exception | None:
        """Turn one batch result into an extraction, tracing it.

        Args:
            recording_id: The recording the result belongs to.
            result: The SDK's per-request batch result.
            elapsed_ms: The batch's wall-clock time, recorded as latency.

        Returns:
            The extraction, the error, or None when the request was cancelled
            or expired and must be extracted live instead.
        """
        if result.type in {"canceled", "expired"}:
            return None
        try:
            with trace_call(
                self._trace_sink,
                recording_id=recording_id,
                stage=PipelineStage.EXTRACTION,
                provider=f"{PROVIDER}-batch",
                model=MODEL,
                prompt_version=CURRENT_PROMPT_VERSION,
            ) as call:
                call.latency_ms = elapsed_ms
                message = _read_message(result)
                usage = message.usage
                call.model = message.model
                call.usage = CallUsage(
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cache_read_tokens=usage.cache_read_input_tokens,
                    cache_write_tokens=usage.cache_creation_input_tokens,
                    batch=True,
                )
                output = parse_output(message)
        except ExtractionFailedError as error:
            return error
        return ExtractionResult(
            output=output, model=message.model, prompt_version=CURRENT_PROMPT_VERSION
        )


def _read_message(result: Any) -> Any:  # noqa: ANN401 - the SDK's result union
    """Return a succeeded result's message.

    Args:
        result: The SDK's per-request batch result.

    Returns:
        The message.

    Raises:
        ExtractionFailedError: When the request errored.
    """
    if result.type == "errored":
        error = getattr(getattr(result, "error", None), "error", None)
        msg = f"batch request errored: {getattr(error, 'type', 'unknown')}"
        raise ExtractionFailedError(msg)
    return result.message
