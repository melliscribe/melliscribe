# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The retention policy: audio only, 12 months by default (FR-027a).

Records and transcripts are kept for the life of the account; only the audio,
the bulkiest and most personal thing held, has a lifespan.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta

from melliscribe.models.account import DEFAULT_RETENTION_DAYS

WARNING_DAYS = 30
"""However old a recording, its audio never expires sooner than this from now,
so the beekeeper is always warned first (FR-027e) — an imported file from last
year, or a shortened retention period, included."""


def compute_expiry(
    captured_at: datetime,
    retention_days: int = DEFAULT_RETENTION_DAYS,
    now: datetime | None = None,
) -> datetime:
    """Return when a recording's audio expires.

    Args:
        captured_at: When the recording was captured.
        retention_days: The account's retention period.
        now: The current time.

    Returns:
        The capture time plus the retention period, but never earlier than
        the warning window from now.
    """
    now = now or datetime.now(UTC)
    return max(
        captured_at + timedelta(days=retention_days),
        now + timedelta(days=WARNING_DAYS),
    )
