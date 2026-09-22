# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GET/POST /hives."""

from __future__ import annotations

from fastapi import APIRouter

from melliscribe.api.deps import SessionDep
from melliscribe.api.errors import ErrorResponse
from melliscribe.db import repository
from melliscribe.models.hive import Hive
from melliscribe.models.hive import HiveCreate

router = APIRouter(prefix="/hives", tags=["hives"])


@router.get("")
def list_hives(session: SessionDep) -> list[Hive]:
    """List the hives.

    Args:
        session: The database session.

    Returns:
        The hives.
    """
    return repository.list_hives(session)


@router.post("", status_code=201, responses={409: {"model": ErrorResponse}})
def create_hive(body: HiveCreate, session: SessionDep) -> Hive:
    """Create a hive from an identifier alone; refuse a duplicate.

    Args:
        body: The identifier.
        session: The database session.

    Returns:
        The new hive.
    """
    return repository.create_hive(session, body.identifier)
