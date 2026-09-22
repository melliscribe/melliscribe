# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Migrations are forward-tested against a seeded database (Principle IV)."""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime

from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import insert
from sqlalchemy import select

from melliscribe.db.migrate import get_revisions
from melliscribe.db.migrate import upgrade
from melliscribe.db.tables import Base
from melliscribe.db.tables import HiveRow


def test_every_migration_applies_in_order_and_keeps_seeded_data(empty_engine):
    hive_id = uuid.uuid4()
    for index, revision in enumerate(get_revisions()):
        upgrade(empty_engine, revision)
        if index == 0:
            with empty_engine.begin() as connection:
                connection.execute(
                    insert(HiveRow).values(
                        id=hive_id,
                        identifier="ruche 1",
                        created_at=datetime.now(UTC),
                    )
                )
    with empty_engine.connect() as connection:
        rows = connection.execute(select(HiveRow.identifier)).all()
    assert [row.identifier for row in rows] == ["ruche 1"]


def test_head_matches_the_orm_metadata(empty_engine):
    """The migrations and the SQLAlchemy tables never drift apart."""
    upgrade(empty_engine, "head")
    with empty_engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []
