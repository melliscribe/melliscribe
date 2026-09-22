# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The /records endpoints: review, correction and confirmation."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from fastapi import APIRouter

from melliscribe.api.deps import SessionDep
from melliscribe.api.errors import AppError
from melliscribe.api.errors import ErrorResponse
from melliscribe.db import repository
from melliscribe.domain.inspection.corrections import OpenFlagsError
from melliscribe.domain.inspection.corrections import apply_patch
from melliscribe.domain.inspection.corrections import confirm_record
from melliscribe.domain.inspection.corrections import resolve_hive as resolve_hive_field
from melliscribe.models.api import RecordPatch
from melliscribe.models.api import RecordView
from melliscribe.models.api import ResolveHive

router = APIRouter(prefix="/records", tags=["records"])

_ERRORS: dict[int | str, dict[str, Any]] = {
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
}


def build_view(session: SessionDep, record_id: uuid.UUID) -> RecordView:
    """Assemble what the review screen needs in one response.

    Args:
        session: The database session.
        record_id: The record.

    Returns:
        The record with its version, transcript and audio availability.
    """
    record, version = repository.get_record(session, record_id)
    recording = repository.get_recording_row(session, record.recording_id)
    transcript = repository.get_transcript(session, record.recording_id)
    return RecordView.model_validate(
        record.model_dump()
        | {
            "version": version,
            "audio_available": recording.audio_available,
            "transcript": transcript,
        }
    )


@router.get("")
def list_records(
    session: SessionDep,
    hive_id: uuid.UUID | None = None,
    confirmed: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[RecordView]:
    """List records, newest inspection first.

    Args:
        session: The database session.
        hive_id: Only this hive.
        confirmed: Only confirmed, or only unconfirmed, records.
        date_from: Only inspections on or after this day.
        date_to: Only inspections on or before this day.

    Returns:
        The records.
    """
    records = repository.list_records(
        session,
        hive_id=hive_id,
        confirmed=confirmed,
        date_from=date_from,
        date_to=date_to,
    )
    return [build_view(session, record.id) for record, _ in records]


@router.get("/{record_id}", responses=_ERRORS)
def get_record(record_id: uuid.UUID, session: SessionDep) -> RecordView:
    """Return one record, with every field's status, phrase and segment.

    Args:
        record_id: The record.
        session: The database session.

    Returns:
        The record.
    """
    return build_view(session, record_id)


@router.patch("/{record_id}", responses=_ERRORS)
def patch_record(
    record_id: uuid.UUID, patch: RecordPatch, session: SessionDep
) -> RecordView:
    """Correct or confirm fields; every field set becomes `CONFIRMED` (FR-010).

    Args:
        record_id: The record.
        patch: The corrections, with the version they are based on.
        session: The database session.

    Returns:
        The corrected record.
    """
    record, _ = repository.get_record(session, record_id)
    repository.save_record(session, apply_patch(record, patch), patch.version)
    return build_view(session, record_id)


@router.post("/{record_id}/confirm", responses=_ERRORS)
def confirm(record_id: uuid.UUID, session: SessionDep) -> RecordView:
    """Confirm the record as a whole. Optional: unconfirmed is a valid state.

    Args:
        record_id: The record.
        session: The database session.

    Returns:
        The confirmed record.

    Raises:
        AppError: When fields still need checking.
    """
    record, version = repository.get_record(session, record_id)
    try:
        confirmed = confirm_record(record)
    except OpenFlagsError as error:
        raise AppError("record_has_open_flags", 409) from error
    repository.save_record(session, confirmed, version)
    return build_view(session, record_id)


@router.post("/{record_id}/resolve-hive", responses=_ERRORS)
def resolve_hive(
    record_id: uuid.UUID, body: ResolveHive, session: SessionDep
) -> RecordView:
    """Resolve a flagged hive by picking one or creating one (FR-015b).

    Creating here is still the beekeeper's explicit action (FR-015c).

    Args:
        record_id: The record.
        body: An existing hive id, or an identifier to create.
        session: The database session.

    Returns:
        The record with its hive confirmed.
    """
    record, version = repository.get_record(session, record_id)
    if body.hive_id is not None:
        hive = repository.get_hive(session, body.hive_id)
    else:
        hive = repository.create_hive(session, str(body.identifier))
    repository.save_record(session, resolve_hive_field(record, hive.id), version)
    return build_view(session, record_id)
