# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Account-level settings."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from melliscribe.models.base import Model
from melliscribe.models.language import Language

DEFAULT_RETENTION_DAYS = 365
"""Twelve months of audio by default (FR-027a)."""

RetentionDays = Annotated[int, Field(ge=1, le=3650)]


class AccountSettings(Model):
    """The beekeeper's settings.

    Attributes:
        language: Applies to every recording; never inferred from the network
            (FR-026).
        audio_retention_days: How long original audio is kept (FR-027a).
    """

    language: Language = Language.FR
    audio_retention_days: RetentionDays = DEFAULT_RETENTION_DAYS


class AccountSettingsUpdate(Model):
    """A partial update of the settings."""

    language: Language | None = None
    audio_retention_days: RetentionDays | None = None
