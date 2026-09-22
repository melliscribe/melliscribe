# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The /recordings endpoints: thin adapters over storage and the pipeline."""

from __future__ import annotations

import re
import uuid
from datetime import UTC
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter
from fastapi import BackgroundTasks
from fastapi import File
from fastapi import Form
from fastapi import Header
from fastapi import Response
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from melliscribe.api.deps import ServicesDep
from melliscribe.api.deps import SessionDep
from melliscribe.api.errors import AppError
from melliscribe.api.errors import ErrorResponse
from melliscribe.db import repository
from melliscribe.db.tables import RecordingRow
from melliscribe.domain.retention.expiry import delete_audio
from melliscribe.domain.retention.expiry import find_due
from melliscribe.domain.retention.policy import compute_expiry
from melliscribe.models.api import EvalConsent
from melliscribe.models.api import ExpiringRecording
from melliscribe.models.api import ReprocessRequest
from melliscribe.models.language import Language
from melliscribe.models.recording import Recording
from melliscribe.models.recording import RecordingState
from melliscribe.pipeline.process import process_recording
from melliscribe.pipeline.queue import run_queue_once

router = APIRouter(prefix="/recordings", tags=["recordings"])

SUPPORTED_AUDIO_FORMATS = frozenset(
    {
        "audio/webm",
        "audio/ogg",
        "audio/mp4",
        "audio/m4a",
        "audio/x-m4a",
        "audio/aac",
        "audio/mpeg",
        "audio/wav",
        "audio/x-wav",
        "audio/wave",
        "audio/flac",
    }
)
"""What the pipeline accepts, including formats the app did not produce (FR-005)."""
MAX_AUDIO_BYTES = 50 * 1024 * 1024
"""Well above a few minutes of speech in any supported format."""


def get_base_format(audio_format: str) -> str:
    """Strip codec parameters from a media type.

    Args:
        audio_format: For example `audio/webm;codecs=opus`.

    Returns:
        The base type, lower-cased: `audio/webm`.
    """
    return audio_format.split(";", 1)[0].strip().lower()


@router.post(
    "",
    status_code=201,
    responses={
        200: {"model": Recording, "description": "Already held; same id."},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def upload_recording(
    id: Annotated[uuid.UUID, Form()],  # noqa: A002 - the contract's field name
    captured_at: Annotated[datetime, Form()],
    duration_seconds: Annotated[float, Form(ge=0)],
    language: Annotated[Language, Form()],
    audio_format: Annotated[str, Form()],
    audio: Annotated[UploadFile, File()],
    response: Response,
    services: ServicesDep,
    background: BackgroundTasks,
) -> Recording:
    """Accept a recording, idempotently on its client-generated id (FR-020).

    Answers 201 or 200 only once the audio is durably stored: only those let
    the phone drop its local copy (FR-003).

    Args:
        id: The client-generated recording id.
        captured_at: When it was captured, with the device's offset.
        duration_seconds: Its length.
        language: The account language at capture.
        audio_format: Its media type as detected on the device.
        audio: The audio.
        response: Used to answer 200 for a repeat.
        services: The application's services.
        background: Where processing is queued.

    Returns:
        The recording.

    Raises:
        AppError: On an unsupported format, an oversize file or a failed write.
    """
    with services.session_factory() as session:
        existing = session.get(RecordingRow, id)
        if existing is not None:
            response.status_code = 200
            return repository.to_recording(existing)
    if get_base_format(audio_format) not in SUPPORTED_AUDIO_FORMATS:
        raise AppError("unsupported_audio_format", 415, audio_format=audio_format)
    data = await audio.read(MAX_AUDIO_BYTES + 1)
    if len(data) > MAX_AUDIO_BYTES:
        raise AppError("audio_too_large", 413)
    try:
        key = services.audio_store.write(id, data)
    except OSError as error:
        raise AppError("storage_unavailable", 503) from error
    try:
        with services.session_factory.begin() as session:
            settings = repository.get_settings(session)
            row = RecordingRow(
                id=id,
                captured_at=captured_at,
                captured_on=captured_at.date(),
                duration_seconds=duration_seconds,
                language=language.value,
                audio_format=audio_format,
                state=RecordingState.UPLOADED.value,
                retention_expires_at=compute_expiry(
                    captured_at, settings.audio_retention_days
                ),
                audio_available=True,
                audio_key=key,
                reprocess_failed=False,
                created_at=datetime.now(captured_at.tzinfo),
            )
            session.add(row)
            session.flush()
            recording = repository.to_recording(row)
    except IntegrityError:
        with services.session_factory() as session:
            response.status_code = 200
            return repository.to_recording(repository.get_recording_row(session, id))
    if services.process_on_upload:
        background.add_task(run_queue_once, services)
    return recording


@router.get("")
def list_recordings(
    session: SessionDep, state: RecordingState | None = None
) -> list[Recording]:
    """List recordings, including what is queued and what failed (FR-018).

    Args:
        session: The database session.
        state: Only recordings in this state.

    Returns:
        The recordings, newest first.
    """
    from sqlalchemy import select  # noqa: PLC0415 - local to the one query

    query = select(RecordingRow).order_by(RecordingRow.captured_at.desc())
    if state is not None:
        query = query.where(RecordingRow.state == state.value)
    return [repository.to_recording(row) for row in session.scalars(query)]


@router.get("/expiring")
def list_expiring(
    session: SessionDep, within_days: int = 30
) -> list[ExpiringRecording]:
    """List recordings whose audio expires soon, flagging the louder warning.

    Args:
        session: The database session.
        within_days: How far ahead to look.

    Returns:
        The recordings, soonest first.
    """
    due = find_due(session, now=datetime.now(UTC), within_days=within_days)
    return [
        ExpiringRecording(
            recording_id=uuid.UUID(d.recording_id),
            expires_at=d.expires_at,
            needs_attention=d.needs_attention,
        )
        for d in due
    ]


@router.get("/{recording_id}", responses={404: {"model": ErrorResponse}})
def get_recording(recording_id: uuid.UUID, session: SessionDep) -> Recording:
    """Return one recording.

    Args:
        recording_id: The recording.
        session: The database session.

    Returns:
        The recording.
    """
    return repository.to_recording(repository.get_recording_row(session, recording_id))


@router.post(
    "/{recording_id}/retry",
    status_code=202,
    responses={404: {"model": ErrorResponse}, 409: {"model": ErrorResponse}},
)
def retry_recording(
    recording_id: uuid.UUID, services: ServicesDep, background: BackgroundTasks
) -> Recording:
    """Re-queue a failed recording, reusing a transcript that succeeded (FR-019a).

    Args:
        recording_id: The recording.
        services: The application's services.
        background: Where processing is queued.

    Returns:
        The recording.

    Raises:
        AppError: When the recording has not failed.
    """
    with services.session_factory() as session:
        row = repository.get_recording_row(session, recording_id)
        if row.state != RecordingState.FAILED.value:
            raise AppError("not_retryable", 409)
        recording = repository.to_recording(row)
    background.add_task(process_recording, services, recording_id)
    return recording


@router.post(
    "/{recording_id}/reprocess",
    status_code=202,
    responses={404: {"model": ErrorResponse}},
)
def reprocess_recording(
    recording_id: uuid.UUID,
    body: ReprocessRequest,
    services: ServicesDep,
    background: BackgroundTasks,
) -> Recording:
    """Re-run the pipeline, optionally in a corrected language (FR-026b).

    Confirmed fields are preserved (FR-026c); on failure the previous record
    stays intact and the recording's `reprocess_failed` says so (FR-019c).

    Args:
        recording_id: The recording.
        body: The corrected language, if any.
        services: The application's services.
        background: Where processing is queued.

    Returns:
        The recording.
    """
    with services.session_factory() as session:
        recording = repository.to_recording(
            repository.get_recording_row(session, recording_id)
        )
    background.add_task(
        process_recording,
        services,
        recording_id,
        language=body.language,
        reprocess=True,
    )
    return recording


_RANGE = re.compile(r"^bytes=(\d*)-(\d*)$")


def parse_range(header: str, size: int) -> tuple[int, int] | None:
    """Parse a single-range `Range` header.

    Args:
        header: The header value, e.g. `bytes=100-199`.
        size: The resource size.

    Returns:
        The inclusive byte range, or None when it cannot be satisfied.
    """
    match = _RANGE.match(header.strip())
    if match is None or match.groups() == ("", ""):
        return None
    first, last = match.groups()
    if first == "":
        start, end = max(0, size - int(last)), size - 1
    else:
        start = int(first)
        end = min(int(last), size - 1) if last else size - 1
    return (start, end) if start <= end < size else None


@router.get(
    "/{recording_id}/audio",
    response_class=Response,
    responses={
        200: {"content": {"audio/*": {}}},
        206: {"content": {"audio/*": {}}},
        410: {"model": ErrorResponse},
    },
)
def get_audio(
    recording_id: uuid.UUID,
    services: ServicesDep,
    range_header: Annotated[str | None, Header(alias="Range")] = None,
) -> Response:
    """Stream the audio, with range requests for per-field playback (FR-023).

    Args:
        recording_id: The recording.
        services: The application's services.
        range_header: An optional `Range` header.

    Returns:
        The audio, or the requested passage.

    Raises:
        AppError: 410 once the audio is deleted or expired (FR-027d).
    """
    with services.session_factory() as session:
        row = repository.get_recording_row(session, recording_id)
        if not row.audio_available:
            raise AppError("audio_gone", 410)
        media_type = row.audio_format
    data = services.audio_store.read(recording_id)
    headers = {"Accept-Ranges": "bytes"}
    if range_header is None:
        return Response(data, media_type=media_type, headers=headers)
    span = parse_range(range_header, len(data))
    if span is None:
        return Response(
            status_code=416, headers=headers | {"Content-Range": f"bytes */{len(data)}"}
        )
    start, end = span
    return Response(
        data[start : end + 1],
        status_code=206,
        media_type=media_type,
        headers=headers | {"Content-Range": f"bytes {start}-{end}/{len(data)}"},
    )


@router.delete(
    "/{recording_id}", status_code=204, responses={404: {"model": ErrorResponse}}
)
def delete_recording_audio(recording_id: uuid.UUID, services: ServicesDep) -> Response:
    """Delete the audio now, whatever the retention setting (FR-027b).

    The transcript and the record are untouched (FR-027c).

    Args:
        recording_id: The recording.
        services: The application's services.

    Returns:
        An empty 204.
    """
    with services.session_factory.begin() as session:
        delete_audio(session, services.audio_store, recording_id)
    return Response(status_code=204)


@router.post("/{recording_id}/eval-consent", responses={404: {"model": ErrorResponse}})
def set_eval_consent(
    recording_id: uuid.UUID, body: EvalConsent, services: ServicesDep
) -> Recording:
    """Record, with its date, whether this recording may be used for evaluation.

    Consent is explicit, separate and per recording (FR-027f); withdrawing it
    clears the date.

    Args:
        recording_id: The recording.
        body: Whether the beekeeper consents.
        services: The application's services.

    Returns:
        The recording.
    """
    with services.session_factory.begin() as session:
        row = repository.get_recording_row(session, recording_id)
        row.eval_consent_at = datetime.now(UTC) if body.consented else None
        return repository.to_recording(row)
