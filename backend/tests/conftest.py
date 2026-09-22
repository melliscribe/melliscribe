# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Shared pytest fixtures."""

from __future__ import annotations

import os
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import MetaData
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from starlette.testclient import TestClient

from melliscribe.api.app import create_app
from melliscribe.api.deps import Services
from melliscribe.db.audio_store import FileAudioStore
from melliscribe.db.migrate import upgrade
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from tests.support.fakes import FakeExtractor
from tests.support.fakes import FakeTranscriber

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from httpx2 import Response
    from sqlalchemy import Engine


@pytest.fixture
def tmp_wd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Run the test inside a fresh temporary working directory.

    Args:
        tmp_path: The pytest temporary directory.
        monkeypatch: The pytest monkeypatch fixture.

    Returns:
        The temporary working directory.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Skip tests marked `live` unless Anthropic credentials are configured.

    Args:
        items: The collected test items.
    """
    if os.environ.get("ANTHROPIC_API_KEY"):
        return
    skip = pytest.mark.skip(reason="ANTHROPIC_API_KEY not set")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
def empty_engine(tmp_path: Path) -> Iterator[Engine]:
    """Provide an engine on an empty database, dropped afterwards.

    Uses `MELLISCRIBE_DATABASE_URL` when set (PostgreSQL in CI), otherwise a
    throwaway SQLite file.

    Args:
        tmp_path: The pytest temporary directory.

    Yields:
        The engine.
    """
    url = os.environ.get(
        "MELLISCRIBE_DATABASE_URL", f"sqlite:///{tmp_path / 'db.sqlite'}"
    )
    engine = create_engine(url)
    try:
        yield engine
    finally:
        with engine.begin() as connection:
            meta = MetaData()
            meta.reflect(bind=connection)
            meta.drop_all(bind=connection)
        engine.dispose()


@dataclass
class ApiHarness:
    """A test client wired to fakes, plus handles on everything behind it."""

    client: TestClient
    services: Services
    transcriber: FakeTranscriber
    extractor: FakeExtractor
    traces: InMemoryTraceSink

    def upload(
        self,
        text: str = "Ruche trois.\nElles sont calmes.",
        *,
        recording_id: uuid.UUID | None = None,
        audio_format: str = "audio/webm;codecs=opus",
        language: str = "fr",
        captured_at: str = "2026-05-12T09:30:00+02:00",
    ) -> Response:
        """Upload a recording whose "audio" is the given text.

        Args:
            text: Stand-in audio, one fake segment per line.
            recording_id: The client-generated id; random when omitted.
            audio_format: The declared media type.
            language: The account language at capture.
            captured_at: The device capture time.

        Returns:
            The HTTP response.
        """
        return self.client.post(
            "/recordings",
            data={
                "id": str(recording_id or uuid.uuid4()),
                "captured_at": captured_at,
                "duration_seconds": "42.5",
                "language": language,
                "audio_format": audio_format,
            },
            files={"audio": ("rec.webm", text.encode(), audio_format)},
        )


@pytest.fixture
def api(empty_engine: Engine, tmp_path: Path) -> Iterator[ApiHarness]:
    """Provide the API over a migrated database, fakes and a temp audio store.

    Args:
        empty_engine: An empty database.
        tmp_path: The pytest temporary directory.

    Yields:
        The harness.
    """
    upgrade(empty_engine)
    transcriber = FakeTranscriber()
    extractor = FakeExtractor()
    traces = InMemoryTraceSink()
    services = Services(
        session_factory=sessionmaker(empty_engine, expire_on_commit=False),
        audio_store=FileAudioStore(tmp_path / "audio"),
        transcriber=transcriber,
        extractor=extractor,
        trace_sink=traces,
    )
    with TestClient(create_app(services)) as client:
        yield ApiHarness(client, services, transcriber, extractor, traces)
