# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Versioned extraction prompts (D6). Files, never inline string literals."""

from __future__ import annotations

from pathlib import Path

from melliscribe.domain.vocabulary.glossary import render_glossary
from melliscribe.models.vocabulary import VOCABULARIES

PROMPTS_DIR = Path(__file__).parent
CURRENT_PROMPT_VERSION = "1"


def list_prompt_versions() -> list[str]:
    """List every prompt version shipped.

    Returns:
        The versions, oldest first.
    """
    return sorted(
        (p.stem.removeprefix("v") for p in PROMPTS_DIR.glob("v*.md")), key=int
    )


def render_vocabularies() -> str:
    """Render the controlled vocabularies as the prompt shows them.

    Returns:
        Every field's active values with definitions, in a stable order.
    """
    lines: list[str] = []
    for name, vocabulary in VOCABULARIES.items():
        lines.append(f"### {name}")
        lines.append(vocabulary.membership)
        lines.extend(
            f"- `{value}`: {vocabulary.definitions[value]}"
            for value in vocabulary.get_active_values()
        )
        lines.append("")
    return "\n".join(lines).rstrip()


def render_system_prompt(version: str = CURRENT_PROMPT_VERSION) -> str:
    """Render one prompt version into the stable, cacheable system prompt.

    The output is byte-identical across calls for a given version, vocabulary
    and glossary: anything volatile here would silently defeat the prompt
    cache (D5).

    Args:
        version: The prompt version.

    Returns:
        The system prompt.

    Raises:
        FileNotFoundError: When the version does not exist.
    """
    path = PROMPTS_DIR / f"v{version}.md"
    if not path.is_file():
        msg = f"no extraction prompt version {version!r}"
        raise FileNotFoundError(msg)
    return (
        path.read_text("utf-8")
        .replace("{{VOCABULARIES}}", render_vocabularies())
        .replace("{{GLOSSARY}}", render_glossary())
    )
