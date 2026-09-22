# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Alembic environment: uses a passed-in connection, or the configured URL."""

from __future__ import annotations

from alembic import context
from sqlalchemy import create_engine

from melliscribe.db.session import get_database_url
from melliscribe.db.tables import Base

config = context.config
target_metadata = Base.metadata


def run_migrations() -> None:
    """Run the migrations online, on the given or configured database."""
    connection = config.attributes.get("connection")
    if connection is not None:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
        return
    engine = create_engine(get_database_url())
    with engine.begin() as new_connection:
        context.configure(connection=new_connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations()
