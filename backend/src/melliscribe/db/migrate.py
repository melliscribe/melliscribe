# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Run Alembic migrations programmatically, against a given engine."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory

if TYPE_CHECKING:
    from sqlalchemy import Engine

MIGRATIONS_DIR = Path(__file__).with_name("migrations")


def build_config() -> Config:
    """Build the Alembic configuration pointing at the packaged migrations.

    Returns:
        The Alembic configuration.
    """
    config = Config()
    config.set_main_option("script_location", str(MIGRATIONS_DIR))
    return config


def get_revisions() -> list[str]:
    """List every revision, oldest first.

    Returns:
        The revision identifiers in application order.
    """
    script = ScriptDirectory.from_config(build_config())
    return [revision.revision for revision in reversed(list(script.walk_revisions()))]


def upgrade(engine: Engine, revision: str = "head") -> None:
    """Upgrade the database behind `engine` to `revision`.

    Args:
        engine: The engine to migrate.
        revision: The target revision.
    """
    config = build_config()
    with engine.begin() as connection:
        config.attributes["connection"] = connection
        command.upgrade(config, revision)
