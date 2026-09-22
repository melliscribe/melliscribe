# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Build the configured transcription backend.

ADR-0002 has not chosen a provider yet, so the only backend is the one that
refuses with an attributable error. When the ADR is Accepted, its adapter is
registered here and selected with `MELLISCRIBE_ASR_PROVIDER`.
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
    msg = f"unknown transcription provider {provider!r} (see ADR-0002)"
    raise ValueError(msg)
