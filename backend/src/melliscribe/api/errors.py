# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""One error shape for every endpoint, localised to the account language.

API error messages are beekeeper-facing text and fall under Principle VIII
(FR-025): the message comes from a catalogue, in the account language, never
from a hard-coded string.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from melliscribe.models.base import Model
from melliscribe.models.language import Language

_CATALOGUE_DIR = Path(__file__).resolve().parents[1] / "i18n"


class ErrorResponse(Model):
    """The error body every endpoint returns.

    Attributes:
        code: A stable, machine-readable code.
        message: The explanation, in the account language.
        details: Optional structured detail, such as validation locations.
    """

    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class AppError(Exception):
    """An expected failure with a stable code and an HTTP status."""

    def __init__(self, code: str, status_code: int, **params: str) -> None:
        super().__init__(code)
        self.code = code
        self.status_code = status_code
        self.params = params


@cache
def load_catalogue(language: Language) -> dict[str, Any]:
    """Load the server catalogue for one language.

    Args:
        language: The language.

    Returns:
        The catalogue.
    """
    return json.loads((_CATALOGUE_DIR / f"{language.value}.json").read_text("utf-8"))


def translate_error(code: str, language: Language, **params: str) -> str:
    """Render an error message.

    Args:
        code: The error code.
        language: The account language.
        **params: Values interpolated into the message.

    Returns:
        The localised message.
    """
    template: str = load_catalogue(language)["error"][code]
    return template.format(**params)


def find_catalogue_gaps() -> list[str]:
    """Find error codes missing in either language.

    Returns:
        One message per missing key.
    """
    keys = {lang: set(load_catalogue(lang)["error"]) for lang in Language}
    everything = set.union(*keys.values())
    return [
        f"server {lang.value}: missing error.{key}"
        for lang, present in keys.items()
        for key in sorted(everything - present)
    ]
