# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Durable audio storage (FR-003).

A write returns only once the bytes are on stable storage: the file is written
to a temporary name, flushed and fsynced, renamed into place, and the directory
is fsynced so the rename itself survives a crash. Only then may the API answer
201 and the phone drop its local copy.

Object storage is the production target (plan.md); this file store is its
development and single-host implementation behind the same small interface.
"""

from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING
from typing import Protocol

if TYPE_CHECKING:
    from pathlib import Path


class AudioStore(Protocol):
    """Where recordings' audio lives."""

    def write(self, recording_id: uuid.UUID | str, data: bytes) -> str:
        """Store audio durably.

        Args:
            recording_id: The recording.
            data: The audio bytes.

        Returns:
            The storage key.
        """
        ...

    def read(self, recording_id: uuid.UUID | str) -> bytes:
        """Read audio.

        Args:
            recording_id: The recording.

        Returns:
            The audio bytes.
        """
        ...

    def delete(self, recording_id: uuid.UUID | str) -> None:
        """Delete audio immediately (FR-027b).

        Args:
            recording_id: The recording.
        """
        ...


class FileAudioStore:
    """Audio as files under one private directory, never in the repository."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def get_path(self, recording_id: uuid.UUID | str) -> Path:
        """Return where a recording's audio lives.

        Args:
            recording_id: The recording.

        Returns:
            The file path.
        """
        return self.root / str(uuid.UUID(str(recording_id)))

    def write(self, recording_id: uuid.UUID | str, data: bytes) -> str:
        """Store audio and return only once it is durable.

        Args:
            recording_id: The recording.
            data: The audio bytes.

        Returns:
            The storage key.
        """
        path = self.get_path(recording_id)
        temporary = path.with_suffix(".partial")
        with temporary.open("wb") as file:
            file.write(data)
            file.flush()
            os.fsync(file.fileno())
        temporary.replace(path)
        directory = os.open(self.root, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
        return path.name

    def read(self, recording_id: uuid.UUID | str) -> bytes:
        """Read audio.

        Args:
            recording_id: The recording.

        Returns:
            The audio bytes.
        """
        return self.get_path(recording_id).read_bytes()

    def delete(self, recording_id: uuid.UUID | str) -> None:
        """Delete audio; a missing file is already deleted.

        Args:
            recording_id: The recording.
        """
        self.get_path(recording_id).unlink(missing_ok=True)
