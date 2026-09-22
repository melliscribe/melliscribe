# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Persistence: rows in, validated Pydantic models out.

Every read goes back through the Pydantic model, so a row that no longer
satisfies the model's invariants fails loudly instead of reaching a beekeeper.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import select

from melliscribe.api.errors import AppError
from melliscribe.db.tables import AccountSettingsRow
from melliscribe.db.tables import HiveRow
from melliscribe.db.tables import InspectionRecordRow
from melliscribe.db.tables import RecordingRow
from melliscribe.db.tables import TranscriptRow
from melliscribe.domain.inspection.hive_match import normalise_identifier
from melliscribe.domain.retention.policy import compute_expiry
from melliscribe.models.account import AccountSettings
from melliscribe.models.hive import Hive
from melliscribe.models.inspection import InspectionRecord
from melliscribe.models.language import Language
from melliscribe.models.recording import Recording
from melliscribe.models.transcript import Transcript

if TYPE_CHECKING:
    from datetime import date

    from sqlalchemy.orm import Session

    from melliscribe.models.account import AccountSettingsUpdate

_SETTINGS_ID = 1


def get_settings(session: Session) -> AccountSettings:
    """Return the account settings, creating the defaults on first use.

    Args:
        session: The database session.

    Returns:
        The settings.
    """
    row = session.get(AccountSettingsRow, _SETTINGS_ID)
    if row is None:
        defaults = AccountSettings()
        row = AccountSettingsRow(
            id=_SETTINGS_ID,
            language=defaults.language.value,
            audio_retention_days=defaults.audio_retention_days,
        )
        session.add(row)
        session.flush()
    return AccountSettings(
        language=Language(row.language), audio_retention_days=row.audio_retention_days
    )


def update_settings(session: Session, update: AccountSettingsUpdate) -> AccountSettings:
    """Apply a partial settings update.

    Args:
        session: The database session.
        update: The fields to change.

    Returns:
        The updated settings.
    """
    get_settings(session)
    row = session.get_one(AccountSettingsRow, _SETTINGS_ID)
    if update.language is not None:
        row.language = update.language.value
    if update.audio_retention_days is not None:
        row.audio_retention_days = update.audio_retention_days
        for recording in session.scalars(
            select(RecordingRow).where(RecordingRow.audio_available.is_(True))
        ):
            recording.retention_expires_at = compute_expiry(
                recording.captured_at, update.audio_retention_days
            )
    session.flush()
    return get_settings(session)


def _to_hive(row: HiveRow) -> Hive:
    return Hive(id=row.id, identifier=row.identifier, created_at=row.created_at)


def list_hives(session: Session) -> list[Hive]:
    """List the beekeeper's hives, by identifier.

    Args:
        session: The database session.

    Returns:
        The hives.
    """
    rows = session.scalars(select(HiveRow).order_by(HiveRow.identifier))
    return [_to_hive(row) for row in rows]


def get_hive(session: Session, hive_id: uuid.UUID) -> Hive:
    """Return one hive.

    Args:
        session: The database session.
        hive_id: The hive.

    Returns:
        The hive.

    Raises:
        AppError: When it does not exist.
    """
    row = session.get(HiveRow, hive_id)
    if row is None:
        raise AppError("hive_not_found", 404)
    return _to_hive(row)


def create_hive(session: Session, identifier: str) -> Hive:
    """Create a hive, refusing an identifier already in use (FR-015d).

    Identifiers that would be matched as the same hive when spoken — "Ruche 3"
    and "3" — count as duplicates, or dictation could not tell them apart.

    Args:
        session: The database session.
        identifier: The trimmed identifier.

    Returns:
        The new hive.

    Raises:
        AppError: When the identifier is already in use.
    """
    key = normalise_identifier(identifier)
    for hive in list_hives(session):
        if normalise_identifier(hive.identifier) == key:
            raise AppError("duplicate_hive", 409, identifier=hive.identifier)
    row = HiveRow(id=uuid.uuid4(), identifier=identifier, created_at=datetime.now(UTC))
    session.add(row)
    session.flush()
    return _to_hive(row)


def to_recording(row: RecordingRow) -> Recording:
    """Convert a recording row.

    Args:
        row: The row.

    Returns:
        The recording.
    """
    return Recording.model_validate(row, from_attributes=True)


def get_recording_row(session: Session, recording_id: uuid.UUID) -> RecordingRow:
    """Return a recording row.

    Args:
        session: The database session.
        recording_id: The recording.

    Returns:
        The row.

    Raises:
        AppError: When it does not exist.
    """
    row = session.get(RecordingRow, recording_id)
    if row is None:
        raise AppError("recording_not_found", 404)
    return row


def get_transcript(session: Session, recording_id: uuid.UUID) -> Transcript | None:
    """Return a recording's transcript, if it has one.

    Args:
        session: The database session.
        recording_id: The recording.

    Returns:
        The transcript, or None.
    """
    row = session.scalar(
        select(TranscriptRow).where(TranscriptRow.recording_id == recording_id)
    )
    if row is None:
        return None
    return Transcript(
        id=row.id,
        recording_id=row.recording_id,
        full_text=row.full_text,
        segments=row.segments,
        language_detected=row.language_detected,
    )


def get_transcript_provenance(
    session: Session, recording_id: uuid.UUID
) -> tuple[str, str]:
    """Return which ASR provider and model produced a transcript.

    Args:
        session: The database session.
        recording_id: The recording.

    Returns:
        The provider and model.
    """
    row = session.scalars(
        select(TranscriptRow).where(TranscriptRow.recording_id == recording_id)
    ).one()
    return row.provider, row.model


def save_transcript(
    session: Session, transcript: Transcript, provider: str, model: str
) -> None:
    """Insert or replace a recording's transcript, keeping its id.

    Args:
        session: The database session.
        transcript: The transcript.
        provider: The ASR provider.
        model: The ASR model.
    """
    row = session.scalar(
        select(TranscriptRow).where(
            TranscriptRow.recording_id == transcript.recording_id
        )
    )
    if row is None:
        row = TranscriptRow(id=transcript.id, recording_id=transcript.recording_id)
        session.add(row)
    row.full_text = transcript.full_text
    row.segments = [s.model_dump(mode="json") for s in transcript.segments]
    row.language_detected = (
        transcript.language_detected.value if transcript.language_detected else None
    )
    row.provider = provider
    row.model = model
    session.flush()


def _to_record(row: InspectionRecordRow) -> InspectionRecord:
    return InspectionRecord.model_validate(row.document)


def get_record(session: Session, record_id: uuid.UUID) -> tuple[InspectionRecord, int]:
    """Return a record and its version.

    Args:
        session: The database session.
        record_id: The record.

    Returns:
        The record and its version, for optimistic concurrency.

    Raises:
        AppError: When it does not exist.
    """
    row = session.get(InspectionRecordRow, record_id)
    if row is None:
        raise AppError("record_not_found", 404)
    return _to_record(row), row.version


def get_record_for_recording(
    session: Session, recording_id: uuid.UUID
) -> tuple[InspectionRecord, int] | None:
    """Return the record derived from a recording, if any.

    Args:
        session: The database session.
        recording_id: The recording.

    Returns:
        The record and its version, or None.
    """
    row = session.scalar(
        select(InspectionRecordRow).where(
            InspectionRecordRow.recording_id == recording_id
        )
    )
    return (_to_record(row), row.version) if row is not None else None


def save_record(
    session: Session, record: InspectionRecord, expected_version: int | None = None
) -> int:
    """Insert or update a record, refusing a concurrent change.

    Args:
        session: The database session.
        record: The record.
        expected_version: The version the change was based on; None skips the
            check (pipeline writes, which merge confirmed fields themselves).

    Returns:
        The new version.

    Raises:
        AppError: When the record changed since `expected_version`.
    """
    row = session.get(InspectionRecordRow, record.id, with_for_update=True)
    if row is None:
        row = InspectionRecordRow(
            id=record.id, recording_id=record.recording_id, version=0
        )
        session.add(row)
    elif expected_version is not None and row.version != expected_version:
        raise AppError("record_changed", 409)
    row.transcript_id = record.transcript_id
    row.hive_id = record.hive_id
    row.inspection_date = record.inspection_date.value
    row.confirmed_at = record.confirmed_at
    row.document = record.model_dump(mode="json")
    row.version += 1
    session.flush()
    return row.version


def list_records(
    session: Session,
    *,
    hive_id: uuid.UUID | None = None,
    confirmed: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[tuple[InspectionRecord, int]]:
    """List records, newest inspection first.

    Args:
        session: The database session.
        hive_id: Only this hive's records.
        confirmed: Only confirmed, or only unconfirmed, records.
        date_from: Only inspections on or after this day.
        date_to: Only inspections on or before this day.

    Returns:
        The records with their versions.
    """
    query = select(InspectionRecordRow)
    if hive_id is not None:
        query = query.where(InspectionRecordRow.hive_id == hive_id)
    if confirmed is not None:
        column = InspectionRecordRow.confirmed_at
        query = query.where(column.is_not(None) if confirmed else column.is_(None))
    if date_from is not None:
        query = query.where(InspectionRecordRow.inspection_date >= date_from)
    if date_to is not None:
        query = query.where(InspectionRecordRow.inspection_date <= date_to)
    query = query.order_by(InspectionRecordRow.inspection_date.desc())
    return [(_to_record(row), row.version) for row in session.scalars(query)]
