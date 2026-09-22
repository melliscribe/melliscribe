# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""What produced a record, so it can be compared and reproduced (FR-011)."""

from __future__ import annotations

from datetime import datetime

from melliscribe.models.base import Model


class Provenance(Model):
    """The interpretation method and versions behind one record.

    Attributes:
        transcription_provider: The ASR provider (ADR-0002).
        transcription_model: The ASR model.
        extraction_model: The model that actually served the extraction.
        prompt_version: The extraction prompt file version.
        vocabulary_version: The controlled vocabulary version.
        extraction_schema_version: The extraction output schema version.
        uncertainty_threshold: The confidence below which a field is flagged
            (FR-008a).
        extracted_at: When extraction ran.
    """

    transcription_provider: str
    transcription_model: str
    extraction_model: str
    prompt_version: str
    vocabulary_version: str
    extraction_schema_version: str
    uncertainty_threshold: float
    extracted_at: datetime
