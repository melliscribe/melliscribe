# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The base class every domain and API model derives from."""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict


class Model(BaseModel):
    """A strict Pydantic model: unknown fields are rejected, not ignored.

    Fields with defaults are still required in serialization schemas, because
    the server always sends them: the generated client types then say so.
    """

    model_config = ConfigDict(
        extra="forbid", json_schema_serialization_defaults_required=True
    )
