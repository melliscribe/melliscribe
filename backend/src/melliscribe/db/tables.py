# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""SQLAlchemy tables. They mirror the Pydantic models; they do not define them.

An inspection record's observation fields are stored as one JSON document
validated by [InspectionRecord][melliscribe.models.inspection.InspectionRecord]
on every read and write, with the columns needed for filtering denormalised
alongside it. Every table that references a recording survives the deletion of
its audio (FR-027c): deleting audio clears a flag, never a row.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import JSON
from sqlalchemy import Boolean
from sqlalchemy import Date
from sqlalchemy import DateTime
from sqlalchemy import Float
from sqlalchemy import ForeignKey
from sqlalchemy import Integer
from sqlalchemy import Numeric
from sqlalchemy import String
from sqlalchemy import Text
from sqlalchemy import Uuid
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy.types import TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """A timestamp stored in UTC and always read back timezone-aware.

    SQLite drops the offset that PostgreSQL keeps; this makes both behave the
    same, so comparisons against `datetime.now(UTC)` never mix naive and aware.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Convert to UTC before storing.

        Args:
            value: The timestamp; must be timezone-aware.
            dialect: Unused.

        Returns:
            The timestamp in UTC.
        """
        del dialect
        return value.astimezone(UTC) if value is not None else None

    def process_result_value(
        self, value: datetime | None, dialect: object
    ) -> datetime | None:
        """Attach UTC to a naive timestamp read back.

        Args:
            value: The stored timestamp.
            dialect: Unused.

        Returns:
            The timezone-aware timestamp.
        """
        del dialect
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value


class Base(DeclarativeBase):
    """The declarative base for every table."""

    type_annotation_map = {  # noqa: RUF012 - SQLAlchemy's documented idiom
        datetime: UTCDateTime(),
        uuid.UUID: Uuid(),
        dict[str, Any]: JSON(),
        list[Any]: JSON(),
    }


class AccountSettingsRow(Base):
    """The single beekeeper's settings (one row, id 1)."""

    __tablename__ = "account_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    language: Mapped[str] = mapped_column(String(2))
    audio_retention_days: Mapped[int] = mapped_column(Integer)


class HiveRow(Base):
    """A hive."""

    __tablename__ = "hives"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    identifier: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime]


class RecordingRow(Base):
    """A recording; its audio lives in the audio store."""

    __tablename__ = "recordings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    captured_at: Mapped[datetime]
    captured_on: Mapped[date] = mapped_column(Date)
    duration_seconds: Mapped[float] = mapped_column(Float)
    language: Mapped[str] = mapped_column(String(2))
    audio_format: Mapped[str] = mapped_column(String(128))
    state: Mapped[str] = mapped_column(String(32), index=True)
    retention_expires_at: Mapped[datetime | None]
    audio_available: Mapped[bool] = mapped_column(Boolean)
    audio_key: Mapped[str | None] = mapped_column(String(256))
    failure_reason: Mapped[str | None] = mapped_column(Text)
    failure_stage: Mapped[str | None] = mapped_column(String(32))
    reprocess_failed: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_consent_at: Mapped[datetime | None]
    created_at: Mapped[datetime]


class TranscriptRow(Base):
    """A transcript. Outlives its recording's audio."""

    __tablename__ = "transcripts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recordings.id"), unique=True
    )
    full_text: Mapped[str] = mapped_column(Text)
    segments: Mapped[list[Any]]
    language_detected: Mapped[str | None] = mapped_column(String(2))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))


class InspectionRecordRow(Base):
    """An inspection record, stored as its validated JSON document."""

    __tablename__ = "inspection_records"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    recording_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("recordings.id"), unique=True
    )
    transcript_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("transcripts.id"))
    hive_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("hives.id"), index=True
    )
    inspection_date: Mapped[date | None] = mapped_column(Date, index=True)
    confirmed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(Integer)
    document: Mapped[dict[str, Any]]


class LLMTraceRow(Base):
    """One traced pipeline call (ADR-0006). Holds no user content."""

    __tablename__ = "llm_trace"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    recording_id: Mapped[uuid.UUID] = mapped_column(index=True)
    stage: Mapped[str] = mapped_column(String(32))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_version: Mapped[str | None] = mapped_column(String(32))
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cache_read_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6))
    rates_checked_on: Mapped[str | None] = mapped_column(String(10))
    latency_ms: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text)
    fallback_taken: Mapped[bool] = mapped_column(Boolean)
    created_at: Mapped[datetime] = mapped_column(index=True)
