# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Database configuration. The URL comes from the environment (Principle III)."""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATA_DIR = Path(os.environ.get("MELLISCRIBE_DATA_DIR", "var"))


def get_database_url() -> str:
    """Return the database URL.

    Returns:
        `MELLISCRIBE_DATABASE_URL`, or a local SQLite file for development.
    """
    url = os.environ.get("MELLISCRIBE_DATABASE_URL")
    if url:
        return url
    DEFAULT_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{DEFAULT_DATA_DIR / 'melliscribe.sqlite'}"
