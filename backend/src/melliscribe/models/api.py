# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""API payloads that are not domain entities.

Still the single source of truth: the OpenAPI schema, and so the frontend
types, are generated from these.
"""

from __future__ import annotations

from datetime import date
from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import Field
from pydantic import model_validator

from melliscribe.models.base import Model
from melliscribe.models.hive import HiveIdentifier
from melliscribe.models.inspection import InspectionRecord
from melliscribe.models.language import Language
from melliscribe.models.transcript import Transcript  # noqa: TC001
from melliscribe.models.vocabulary import BroodState
from melliscribe.models.vocabulary import QueenSeen
from melliscribe.models.vocabulary import StoresState
from melliscribe.models.vocabulary import Temperament


class RecordView(InspectionRecord):
    """A record as the review screen needs it, in one call.

    Attributes:
        version: For optimistic concurrency on PATCH.
        audio_available: Whether playback can be offered (FR-027d).
        transcript: The full transcript the record came from (FR-012).
    """

    version: int
    audio_available: bool
    transcript: Transcript


class TreatmentInput(Model):
    """A treatment as the beekeeper enters or corrects it."""

    product: str = Field(min_length=1)
    dose: str = ""
    applied_on: date | None = None


class RecordPatch(Model):
    """A correction. Every field present becomes `CONFIRMED` (FR-010).

    Send a field with `null` to confirm that it was not observed. Omit a field
    to leave it untouched.
    """

    version: int
    inspection_date: date | None = None
    queen_seen: QueenSeen | None = None
    brood: BroodState | None = None
    stores: StoresState | None = None
    temperament: Temperament | None = None
    treatments: list[TreatmentInput] | None = None
    actions_to_do: list[str] | None = None


class ResolveHive(Model):
    """Resolve a flagged hive: pick one, or create one (FR-015b)."""

    hive_id: UUID | None = None
    identifier: HiveIdentifier | None = None

    @model_validator(mode="after")
    def _check_choice(self) -> Self:
        """Require exactly one of `hive_id` and `identifier`.

        Returns:
            The validated request.

        Raises:
            ValueError: When both or neither are given.
        """
        if (self.hive_id is None) == (self.identifier is None):
            msg = "give exactly one of hive_id and identifier"
            raise ValueError(msg)
        return self


class ReprocessRequest(Model):
    """Re-run the pipeline, optionally against a corrected language (FR-026b)."""

    language: Language | None = None


class ExpiringRecording(Model):
    """A recording whose audio will soon be deleted (FR-027e).

    Attributes:
        recording_id: The recording.
        expires_at: When its audio will be deleted.
        needs_attention: The audio is still the evidence for unconfirmed or
            flagged fields, or was never processed — warn louder.
    """

    recording_id: UUID
    expires_at: datetime
    needs_attention: bool


class EvalConsent(Model):
    """The beekeeper's explicit, separate consent to evaluation use (FR-027f)."""

    consented: bool
