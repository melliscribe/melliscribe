# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The Principle VIII gate: labels, catalogues, glossary and released values."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from melliscribe.api.errors import find_catalogue_gaps
from melliscribe.domain.vocabulary.glossary import find_incomplete_terms
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.language import Language
from melliscribe.models.vocabulary import VOCABULARIES
from melliscribe.models.vocabulary import check_released_values

DEFAULT_CATALOGUE_DIR = Path(
    os.environ.get(
        "MELLISCRIBE_CATALOGUE_DIR",
        Path(__file__).resolve().parents[5] / "frontend" / "src" / "i18n",
    )
)
"""The frontend catalogues, which hold every beekeeper-facing label."""


def _flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """Flatten a nested catalogue into dotted keys.

    Args:
        tree: The nested catalogue.
        prefix: The dotted prefix of `tree`.

    Returns:
        The leaves of the catalogue keyed by dotted path.
    """
    flat: dict[str, Any] = {}
    for key, value in tree.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{path}."))
        else:
            flat[path] = value
    return flat


def get_required_label_keys() -> list[str]:
    """List the keys every catalogue must hold for language-neutral codes.

    Returns:
        The dotted keys for every vocabulary value, status and flag reason.
    """
    keys = [
        f"vocabulary.{name}.{value.value}"
        for name, vocabulary in VOCABULARIES.items()
        for value in vocabulary.values
    ]
    keys += [f"status.{status.value}" for status in FieldStatus]
    keys += [f"flag_reason.{reason.value}" for reason in FlagReason]
    keys += [f"language.{language.value}" for language in Language]
    return keys


def find_vocabulary_gaps(catalogue_dir: Path = DEFAULT_CATALOGUE_DIR) -> list[str]:
    """Find every way the vocabularies and catalogues are incomplete.

    Args:
        catalogue_dir: The directory holding `fr.json` and `en.json`.

    Returns:
        One message per gap; empty when the build may proceed.
    """
    catalogues = {
        language: _flatten(
            json.loads((catalogue_dir / f"{language.value}.json").read_text("utf-8"))
        )
        for language in Language
    }
    gaps: list[str] = []
    for language, catalogue in catalogues.items():
        gaps.extend(
            f"{language.value}: missing label {key}"
            for key in get_required_label_keys()
            if key not in catalogue
        )
        for other_language, other in catalogues.items():
            if other_language is language:
                continue
            gaps.extend(
                f"{language.value}: missing key {key}"
                for key in other
                if key not in catalogue and key not in get_required_label_keys()
            )
        gaps.extend(
            f"{language.value}: empty label {key}"
            for key, label in catalogue.items()
            if not isinstance(label, str) or not label.strip()
        )
    gaps.extend(
        f"{name}.{value.value}: no documented definition"
        for name, vocabulary in VOCABULARIES.items()
        for value in vocabulary.values
        if value.value not in vocabulary.definitions
    )
    gaps.extend(find_incomplete_terms())
    gaps.extend(find_catalogue_gaps())
    gaps.extend(check_released_values())
    return gaps
