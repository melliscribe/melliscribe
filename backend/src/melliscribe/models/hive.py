# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The colony: in this feature, an identifier and nothing else."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import StringConstraints

from melliscribe.models.base import Model

HiveIdentifier = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)
]
"""What the beekeeper says out loud. Non-empty and trimmed."""


class HiveCreate(Model):
    """A request to create a hive: an identifier and nothing else (FR-015a)."""

    identifier: HiveIdentifier


class Hive(Model):
    """A hive. Never created by the system (FR-015c).

    Attributes:
        id: Server-assigned identifier.
        identifier: Unique among the beekeeper's hives (FR-015d).
        created_at: When it was created.
    """

    id: UUID
    identifier: HiveIdentifier
    created_at: datetime
