# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The retention policy: audio only, 12 months by default (FR-027a).

Records and transcripts are kept for the life of the account; only the audio,
the bulkiest and most personal thing held, has a lifespan.
"""

from __future__ import annotations

from datetime import datetime
from datetime import timedelta

from melliscribe.models.account import DEFAULT_RETENTION_DAYS


def compute_expiry(
    captured_at: datetime, retention_days: int = DEFAULT_RETENTION_DAYS
) -> datetime:
    """Return when a recording's audio expires.

    Args:
        captured_at: When the recording was captured.
        retention_days: The account's retention period.

    Returns:
        The expiry time.
    """
    return captured_at + timedelta(days=retention_days)
