# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""GET/PATCH /settings."""

from __future__ import annotations

from fastapi import APIRouter

from melliscribe.api.deps import SessionDep
from melliscribe.db import repository
from melliscribe.models.account import AccountSettings
from melliscribe.models.account import AccountSettingsUpdate

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(session: SessionDep) -> AccountSettings:
    """Return the settings. The language is never inferred from the request.

    Args:
        session: The database session.

    Returns:
        The settings.
    """
    return repository.get_settings(session)


@router.patch("")
def update_settings(
    update: AccountSettingsUpdate, session: SessionDep
) -> AccountSettings:
    """Change the language or the audio retention period.

    Args:
        update: The fields to change.
        session: The database session.

    Returns:
        The updated settings.
    """
    return repository.update_settings(session, update)
