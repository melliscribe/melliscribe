# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""ADR-0003, D5: the prompt prefix is actually cached. Calls the real API."""

from __future__ import annotations

from datetime import date

import pytest

from melliscribe.models.language import Language
from melliscribe.pipeline.extraction.claude import ClaudeExtractor
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from tests.support.builders import build_transcript


@pytest.mark.live
def test_the_second_call_reads_the_cached_prefix():
    """A zero here means every call pays full price for the prefix."""
    sink = InMemoryTraceSink()
    extractor = ClaudeExtractor(sink)
    first = build_transcript("Ruche trois.", "Elles sont calmes, reine vue.")
    second = build_transcript("Hive B2.", "Calm bees, queen not seen.")
    extractor.extract(first, Language.FR, date(2026, 5, 12))
    extractor.extract(second, Language.EN, date(2026, 5, 12))
    assert (sink.traces[1].cache_read_tokens or 0) > 0
