# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Pure scoring functions: no model calls, fully unit-tested."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.domain.inspection.status import normalise_text
from melliscribe.models.inspection import FieldStatus
from melliscribe.models.inspection import ObservationField

if TYPE_CHECKING:
    from melliscribe.evals.dataset import ExtractionCase

_SET_STATUSES = {FieldStatus.SYSTEM_DERIVED, FieldStatus.CONFIRMED}


@dataclass
class CaseOutcome:
    """How one extraction case scored.

    Attributes:
        case_id: The case.
        language: The case's language.
        pair_id: The pair it belongs to, if any.
        correct: Per expected field, whether status and value both matched.
        unmentioned_populated: Fields expected `UNKNOWN` that carried a value
            or proposal — SC-004 violations.
        is_inspection_correct: Whether a record was produced exactly when one
            was expected.
        values: The coded values set on the record, for SC-011.
        error: The extraction error, when the case failed outright.
    """

    case_id: str
    language: str
    pair_id: str | None
    correct: dict[str, bool]
    unmentioned_populated: list[str]
    is_inspection_correct: bool
    values: dict[str, str | None]
    error: str | None = None


def _as_text(value: Any) -> str | None:  # noqa: ANN401 - any coded value
    """Render a coded value for comparison.

    Args:
        value: The value.

    Returns:
        Its string form, or None.
    """
    if value is None:
        return None
    return str(getattr(value, "value", value))


def score_case(
    case: ExtractionCase, fields: dict[str, ObservationField[Any]] | None
) -> CaseOutcome:
    """Score one case against the fields the pipeline produced.

    A field counts as accurate only when both its status and its value match
    the reference (SC-005).

    Args:
        case: The case with its reference outcome.
        fields: The produced fields by name, or None when no record was made.

    Returns:
        The case outcome.
    """
    expected = case.expected
    correct: dict[str, bool] = {}
    populated: list[str] = []
    values: dict[str, str | None] = {}
    for name, reference in expected.fields.items():
        actual = fields.get(name) if fields is not None else None
        if actual is None:
            correct[name] = False
            continue
        value = _as_text(actual.value)
        if actual.status in _SET_STATUSES:
            values[name] = value
        if reference.status is FieldStatus.UNKNOWN and (
            actual.value is not None or actual.proposal is not None
        ):
            populated.append(name)
        status_ok = actual.status is reference.status
        compared = (
            value if actual.status in _SET_STATUSES else _as_text(actual.proposal)
        )
        value_ok = reference.value is None or compared == reference.value
        correct[name] = status_ok and value_ok
    return CaseOutcome(
        case_id=case.id,
        language=case.language.value,
        pair_id=case.pair_id,
        correct=correct,
        unmentioned_populated=populated,
        is_inspection_correct=(fields is not None) == expected.is_inspection,
        values=values,
    )


@dataclass
class ExtractionSummary:
    """Aggregate extraction metrics.

    Attributes:
        cases: How many cases ran, per language.
        accuracy: Field accuracy per language, in percent (SC-005).
        parity_gap: The absolute accuracy gap between languages, in points.
        unmentioned_populated: `case.field` for every SC-004 violation.
        paired_disagreements: `pair.field` where paired cases set different
            coded values on a field both cover (SC-011).
        errors: `case: error` for every case that failed outright.
    """

    cases: dict[str, int] = field(default_factory=dict)
    accuracy: dict[str, float] = field(default_factory=dict)
    parity_gap: float | None = None
    unmentioned_populated: list[str] = field(default_factory=list)
    paired_disagreements: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def summarise_extraction(outcomes: list[CaseOutcome]) -> ExtractionSummary:
    """Aggregate case outcomes into the gated metrics.

    Args:
        outcomes: One outcome per case.

    Returns:
        The summary.
    """
    summary = ExtractionSummary()
    judged: dict[str, list[bool]] = defaultdict(list)
    pairs: dict[str, list[CaseOutcome]] = defaultdict(list)
    for outcome in outcomes:
        summary.cases[outcome.language] = summary.cases.get(outcome.language, 0) + 1
        judged[outcome.language].extend(outcome.correct.values())
        judged[outcome.language].append(outcome.is_inspection_correct)
        summary.unmentioned_populated.extend(
            f"{outcome.case_id}.{name}" for name in outcome.unmentioned_populated
        )
        if outcome.error:
            summary.errors.append(f"{outcome.case_id}: {outcome.error}")
        if outcome.pair_id:
            pairs[outcome.pair_id].append(outcome)
    summary.accuracy = {
        language: round(100 * sum(marks) / len(marks), 2)
        for language, marks in judged.items()
        if marks
    }
    if len(summary.accuracy) == 2:  # noqa: PLR2004 - French and English
        first, second = summary.accuracy.values()
        summary.parity_gap = round(abs(first - second), 2)
    for pair_id, members in sorted(pairs.items()):
        shared = set.intersection(*(set(m.values) for m in members))
        for name in sorted(shared):
            if len({m.values[name] for m in members}) > 1:
                summary.paired_disagreements.append(f"{pair_id}.{name}")
    return summary


def compute_word_error_rate(reference: str, hypothesis: str) -> float:
    """Compute the word error rate, in percent.

    Args:
        reference: The reference transcript.
        hypothesis: The produced transcript.

    Returns:
        Word-level edit distance over reference length, times 100.
    """
    ref = normalise_text(reference).split()
    hyp = normalise_text(hypothesis).split()
    if not ref:
        return 0.0 if not hyp else 100.0
    previous = list(range(len(hyp) + 1))
    for i, ref_word in enumerate(ref, start=1):
        current = [i]
        for j, hyp_word in enumerate(hyp, start=1):
            current.append(
                min(
                    previous[j] + 1,
                    current[j - 1] + 1,
                    previous[j - 1] + (ref_word != hyp_word),
                )
            )
        previous = current
    return round(100 * previous[-1] / len(ref), 2)


def find_glossary_hits(terms: list[str], hypothesis: str) -> dict[str, bool]:
    """Check which glossary terms the transcript recognised (SC-010).

    Args:
        terms: The glossary terms spoken in the audio.
        hypothesis: The produced transcript.

    Returns:
        Whether each term appears in the transcript.
    """
    haystack = f" {normalise_text(hypothesis)} "
    return {term: f" {normalise_text(term)} " in haystack for term in terms}
