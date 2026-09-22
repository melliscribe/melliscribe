# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The wiring of one running application: storage, stages and tracing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import sessionmaker

    from melliscribe.db.audio_store import AudioStore
    from melliscribe.pipeline.extraction.base import BatchExtractor
    from melliscribe.pipeline.extraction.base import Extractor
    from melliscribe.pipeline.tracing.writer import TraceSink
    from melliscribe.pipeline.transcription.base import TranscriptionBackend


@dataclass
class Services:
    """Everything the API and the pipeline need, injected rather than global.

    Attributes:
        session_factory: Opens database sessions.
        audio_store: Holds recordings' audio.
        transcriber: The transcription stage (ADR-0002).
        extractor: The extraction stage (ADR-0003).
        trace_sink: Where pipeline calls are traced (ADR-0006).
        batch_extractor: The deferred extraction path for a backlog (D4).
        process_on_upload: Run a queue pass as soon as a recording arrives.
    """

    session_factory: sessionmaker
    audio_store: AudioStore
    transcriber: TranscriptionBackend
    extractor: Extractor
    trace_sink: TraceSink
    batch_extractor: BatchExtractor | None = None
    process_on_upload: bool = True
