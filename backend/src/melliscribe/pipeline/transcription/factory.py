# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the configured transcription backend.

ADR-0002 has not chosen a provider yet. The default refuses every call with an
attributable error; `MELLISCRIBE_ASR_PROVIDER=faster-whisper` selects the
provisional self-hosted candidate (model from `MELLISCRIBE_ASR_MODEL`, default
`small`), which needs the `asr-local` extra.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from melliscribe.pipeline.transcription.base import UnconfiguredTranscriptionBackend

if TYPE_CHECKING:
    from melliscribe.pipeline.transcription.base import TranscriptionBackend


def build_transcription_backend() -> TranscriptionBackend:
    """Return the backend named by `MELLISCRIBE_ASR_PROVIDER`.

    Returns:
        The configured backend.

    Raises:
        ValueError: When the named provider is not registered.
    """
    provider = os.environ.get("MELLISCRIBE_ASR_PROVIDER", "unconfigured")
    if provider == "unconfigured":
        return UnconfiguredTranscriptionBackend()
    if provider == "faster-whisper":
        from melliscribe.pipeline.transcription.faster_whisper import (  # noqa: PLC0415
            DEFAULT_MODEL,
        )
        from melliscribe.pipeline.transcription.faster_whisper import (  # noqa: PLC0415
            FasterWhisperBackend,
        )

        return FasterWhisperBackend(
            os.environ.get("MELLISCRIBE_ASR_MODEL", DEFAULT_MODEL)
        )
    msg = f"unknown transcription provider {provider!r} (see ADR-0002)"
    raise ValueError(msg)
