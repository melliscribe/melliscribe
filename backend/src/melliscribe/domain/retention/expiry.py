# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Audio expiry and deletion (FR-027b-e).

Deleting audio clears a flag and a file; it never touches the transcript or the
record (FR-027c). The beekeeper is warned before expiry removes anything, and
warned louder when the audio is the only evidence left for an open question —
a record with unconfirmed or flagged fields, or a recording never processed
(FR-027e).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlalchemy import select

from melliscribe.db import repository
from melliscribe.db.tables import RecordingRow
from melliscribe.domain.inspection.corrections import count_open_flags
from melliscribe.domain.inspection.corrections import list_fields
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.recording import RecordingState

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from melliscribe.db.audio_store import AudioStore
    from melliscribe.models.inspection import InspectionRecord

_UNPROCESSED = {
    RecordingState.PENDING_UPLOAD,
    RecordingState.UPLOADED,
    RecordingState.TRANSCRIBING,
    RecordingState.EXTRACTING,
    RecordingState.FAILED,
}


@dataclass(frozen=True)
class DueRecording:
    """A recording whose audio will expire soon.

    Attributes:
        recording_id: The recording.
        expires_at: When its audio will be deleted.
        needs_attention: Whether the audio is still the evidence for an open
            question — the louder warning.
    """

    recording_id: str
    expires_at: datetime
    needs_attention: bool


def has_unsettled_fields(record: InspectionRecord) -> bool:
    """Tell whether a record still has fields the beekeeper has not settled.

    Args:
        record: The record.

    Returns:
        True when a field is still system-derived or uncertain, or the hive is
        unresolved. Fields the dictation never covered do not count.
    """
    if count_open_flags(record):
        return True
    return any(f.status is FieldStatus.SYSTEM_DERIVED for f in list_fields(record))


def find_due(
    session: Session, *, now: datetime, within_days: int
) -> list[DueRecording]:
    """List recordings whose audio expires within the window.

    Args:
        session: The database session.
        now: The current time.
        within_days: How far ahead to look.

    Returns:
        The due recordings, soonest first.
    """
    horizon = now + timedelta(days=within_days)
    rows = session.scalars(
        select(RecordingRow)
        .where(RecordingRow.audio_available.is_(True))
        .where(RecordingRow.retention_expires_at <= horizon)
        .order_by(RecordingRow.retention_expires_at)
    )
    due: list[DueRecording] = []
    for row in rows:
        existing = repository.get_record_for_recording(session, row.id)
        if existing is None:
            attention = RecordingState(row.state) in _UNPROCESSED
        else:
            attention = has_unsettled_fields(existing[0])
        expires_at = row.retention_expires_at
        assert expires_at is not None  # noqa: S101 - filtered by the query
        due.append(DueRecording(str(row.id), expires_at, attention))
    return due


def delete_audio(session: Session, store: AudioStore, recording_id: uuid.UUID) -> None:
    """Delete a recording's audio now, keeping transcript and record (FR-027c).

    Args:
        session: The database session.
        store: The audio store.
        recording_id: The recording.
    """
    row = repository.get_recording_row(session, recording_id)
    store.delete(recording_id)
    row.audio_available = False
    row.retention_expires_at = None


def apply_expiry(
    session: Session, store: AudioStore, *, now: datetime, dry_run: bool = False
) -> list[str]:
    """Delete every audio file past its expiry.

    Args:
        session: The database session.
        store: The audio store.
        now: The current time.
        dry_run: Report without deleting.

    Returns:
        The recordings whose audio was (or would be) deleted.
    """
    expired = [
        d for d in find_due(session, now=now, within_days=0) if d.expires_at <= now
    ]
    if not dry_run:
        for item in expired:
            delete_audio(session, store, uuid.UUID(item.recording_id))
    return [item.recording_id for item in expired]
