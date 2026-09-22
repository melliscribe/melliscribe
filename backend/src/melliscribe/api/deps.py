# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""FastAPI dependencies: the injected services and a request-scoped session."""

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Annotated

from fastapi import Depends
from fastapi import Request
from sqlalchemy.orm import Session

from melliscribe.services import Services

if TYPE_CHECKING:
    from collections.abc import Iterator


def get_services(request: Request) -> Services:
    """Return the application's services.

    Args:
        request: The current request.

    Returns:
        The services the app was created with.
    """
    return request.app.state.services


def get_session(
    services: Annotated[Services, Depends(get_services)],
) -> Iterator[Session]:
    """Open a session for one request, committed when the handler succeeds.

    Args:
        services: The application's services.

    Yields:
        The session.
    """
    with services.session_factory.begin() as session:
        yield session


ServicesDep = Annotated[Services, Depends(get_services)]
SessionDep = Annotated[Session, Depends(get_session)]

__all__ = ["Services", "ServicesDep", "SessionDep"]
