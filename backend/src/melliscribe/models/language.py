# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The supported dictation and display languages (Principle VIII)."""

from __future__ import annotations

from enum import StrEnum


class Language(StrEnum):
    """A supported language, as an ISO 639-1 code."""

    FR = "fr"
    EN = "en"
