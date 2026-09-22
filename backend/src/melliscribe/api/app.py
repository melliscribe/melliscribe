# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The FastAPI application.

Its OpenAPI schema is generated from the Pydantic models and, in turn,
generates the frontend's types (Principle IV).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi import FastAPI
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from melliscribe.api import hives
from melliscribe.api import recordings
from melliscribe.api import records
from melliscribe.api import settings
from melliscribe.api.errors import AppError
from melliscribe.api.errors import ErrorResponse
from melliscribe.api.errors import translate_error
from melliscribe.db import repository
from melliscribe.db.audio_store import FileAudioStore
from melliscribe.db.session import DEFAULT_DATA_DIR
from melliscribe.db.session import get_database_url
from melliscribe.models.language import Language
from melliscribe.services import Services

if TYPE_CHECKING:
    from melliscribe.pipeline.extraction.base import Extractor

API_VERSION = "1.0.0"
"""Versioned independently of the app: phones update on the user's schedule."""


def _get_account_language(request: Request) -> Language:
    """Return the account language for localising an error.

    Args:
        request: The failing request.

    Returns:
        The account language; French if the settings cannot be read.
    """
    services: Services = request.app.state.services
    try:
        with services.session_factory() as session:
            return repository.get_settings(session).language
    except Exception:  # noqa: BLE001 - an error path must not raise again
        return Language.FR


def _render_error(request: Request, error: AppError) -> JSONResponse:
    language = _get_account_language(request)
    body = ErrorResponse(
        code=error.code, message=translate_error(error.code, language, **error.params)
    )
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=error.status_code
    )


def _render_validation_error(
    request: Request, error: RequestValidationError
) -> JSONResponse:
    language = _get_account_language(request)
    body = ErrorResponse(
        code="validation_error",
        message=translate_error("validation_error", language),
        details=[{"loc": list(e["loc"]), "type": e["type"]} for e in error.errors()],
    )
    return JSONResponse(body.model_dump(exclude_none=True), status_code=422)


def create_app(services: Services | None = None) -> FastAPI:
    """Create the application.

    Args:
        services: The wiring; built from the environment when omitted.

    Returns:
        The application.
    """
    app = FastAPI(title="Melliscribe", version=API_VERSION)
    app.state.services = services or build_services()
    app.add_exception_handler(AppError, _render_error)  # ty: ignore[invalid-argument-type]
    app.add_exception_handler(
        RequestValidationError,
        _render_validation_error,  # ty: ignore[invalid-argument-type]
    )
    for module in (settings, hives, recordings, records):
        app.include_router(module.router)
    return app


def build_services() -> Services:
    """Wire the services from the environment.

    Returns:
        The services: configured database, audio store, stages and tracing.
    """
    from melliscribe.pipeline.extraction.claude import ClaudeExtractor  # noqa: PLC0415
    from melliscribe.pipeline.tracing.writer import DatabaseTraceSink  # noqa: PLC0415
    from melliscribe.pipeline.transcription.factory import (  # noqa: PLC0415
        build_transcription_backend,
    )

    session_factory = sessionmaker(
        create_engine(get_database_url()), expire_on_commit=False
    )
    trace_sink = DatabaseTraceSink(session_factory)
    from melliscribe.pipeline.extraction.batch import (  # noqa: PLC0415
        ClaudeBatchExtractor,
    )

    extractor: Extractor = ClaudeExtractor(trace_sink)
    audio_dir = Path(
        os.environ.get("MELLISCRIBE_AUDIO_DIR", DEFAULT_DATA_DIR / "audio")
    )
    return Services(
        session_factory=session_factory,
        audio_store=FileAudioStore(audio_dir),
        transcriber=build_transcription_backend(),
        extractor=extractor,
        trace_sink=trace_sink,
        batch_extractor=ClaudeBatchExtractor(trace_sink),
        # Off: only `melliscribe worker` processes, keeping CPU-heavy local
        # transcription out of the API server's threads.
        process_on_upload=os.environ.get(
            "MELLISCRIBE_PROCESS_ON_UPLOAD", "true"
        ).lower()
        != "false",
    )
