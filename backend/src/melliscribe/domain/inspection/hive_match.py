# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Hive identity from a spoken identifier (FR-015, FR-015c, FR-015e).

Exactly one hive per record. Several hives, or a name matching none, flags the
field; the system never guesses among hives and never creates one.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from melliscribe.domain.inspection.status import normalise_text
from melliscribe.domain.inspection.status import resolve_phrases
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import FlagReason
from melliscribe.models.inspection import ObservationField

if TYPE_CHECKING:
    from collections.abc import Sequence

    from melliscribe.models.hive import Hive
    from melliscribe.models.transcript import Transcript
    from melliscribe.pipeline.extraction.schema import ExtractionOutput

_HIVE_WORDS = {"ruche", "ruchette", "hive", "nuc", "numero", "number", "no", "n"}
_NUMBER_WORDS = {
    **dict.fromkeys(["zero"], "0"),
    **dict.fromkeys(["un", "une", "one"], "1"),
    **dict.fromkeys(["deux", "two"], "2"),
    **dict.fromkeys(["trois", "three"], "3"),
    **dict.fromkeys(["quatre", "four"], "4"),
    **dict.fromkeys(["cinq", "five"], "5"),
    **dict.fromkeys(["six"], "6"),
    **dict.fromkeys(["sept", "seven"], "7"),
    **dict.fromkeys(["huit", "eight"], "8"),
    **dict.fromkeys(["neuf", "nine"], "9"),
    **dict.fromkeys(["dix", "ten"], "10"),
    **dict.fromkeys(["onze", "eleven"], "11"),
    **dict.fromkeys(["douze", "twelve"], "12"),
    **dict.fromkeys(["treize", "thirteen"], "13"),
    **dict.fromkeys(["quatorze", "fourteen"], "14"),
    **dict.fromkeys(["quinze", "fifteen"], "15"),
    **dict.fromkeys(["seize", "sixteen"], "16"),
    **dict.fromkeys(["vingt", "twenty"], "20"),
}


def normalise_identifier(identifier: str) -> str:
    """Normalise a hive identifier for comparison.

    Case, accents, spacing and the word for "hive" are ignored, and number
    words in either language become digits, so "Ruche trois" matches "3".

    Args:
        identifier: The identifier, spoken or stored.

    Returns:
        The comparison key.
    """
    words = normalise_text(identifier).split()
    kept = [_NUMBER_WORDS.get(word, word) for word in words if word not in _HIVE_WORDS]
    return " ".join(kept or words)


def resolve_hive(
    output: ExtractionOutput, transcript: Transcript, hives: Sequence[Hive]
) -> tuple[ObservationField[uuid.UUID], str | None]:
    """Resolve the record's hive from what was said.

    Args:
        output: The extraction output.
        transcript: The transcript it came from.
        hives: The beekeeper's hives.

    Returns:
        The hive field, and the single identifier as said (None when no hive
        or several hives were named).
    """
    mentions = output.hive_mentions
    if not mentions:
        return ObservationField[uuid.UUID](status=FieldStatus.UNKNOWN), None
    verbatim, refs, _ = resolve_phrases([m.phrase for m in mentions], transcript)
    distinct = {normalise_identifier(m.identifier) for m in mentions}
    if output.covers_multiple_hives or len(distinct) > 1:
        return ObservationField[uuid.UUID](
            status=FieldStatus.UNCERTAIN,
            verbatim=_deduplicate(verbatim),
            segment_refs=refs,
            flag_reason=FlagReason.MULTIPLE_HIVES,
        ), None
    spoken = mentions[0].identifier
    key = distinct.pop()
    matches = [hive for hive in hives if normalise_identifier(hive.identifier) == key]
    if len(matches) == 1:
        return ObservationField[uuid.UUID](
            status=FieldStatus.SYSTEM_DERIVED,
            value=matches[0].id,
            verbatim=_deduplicate(verbatim),
            segment_refs=refs,
        ), spoken
    return ObservationField[uuid.UUID](
        status=FieldStatus.UNCERTAIN,
        verbatim=_deduplicate(verbatim),
        segment_refs=refs,
        flag_reason=FlagReason.NO_MATCHING_HIVE,
    ), spoken


def _deduplicate(texts: list[str]) -> list[str]:
    """Drop repeated phrases, keeping first occurrences in order.

    Args:
        texts: The phrases.

    Returns:
        The phrases without repeats.
    """
    return list(dict.fromkeys(texts))
