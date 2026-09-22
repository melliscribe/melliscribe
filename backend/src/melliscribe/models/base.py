# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The base class every domain and API model derives from."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class Model(BaseModel):
    """A strict Pydantic model: unknown fields are rejected, not ignored."""

    model_config = ConfigDict(extra="forbid")
