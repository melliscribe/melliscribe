# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""The pass/fail gates, per stage (ADR-0005)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from melliscribe.evals.scoring import ExtractionSummary

PARITY_GAP_POINTS = 5.0
"""SC-005: French within 5 points of English."""
PARITY_FLOOR = 50
"""Below this many cases per language, the parity gap is reported, not gated."""
GLOSSARY_RECALL_PERCENT = 95.0
"""SC-010."""
REGRESSION_TOLERANCE_POINTS = 2.0
"""Accuracy may drop this much against the baseline before the merge blocks,
absorbing run-to-run model variance. Larger drops need a written trade-off."""
WER_TOLERANCE_POINTS = 1.0


def check_extraction_gates(
    summary: ExtractionSummary, baseline: ExtractionSummary | None
) -> list[str]:
    """List every extraction gate the run fails.

    Args:
        summary: This run.
        baseline: The recorded baseline, if any.

    Returns:
        One message per failed gate; empty when the run passes.
    """
    failures: list[str] = []
    if summary.unmentioned_populated:
        failures.append(
            "SC-004: fields populated from unmentioned content: "
            + ", ".join(summary.unmentioned_populated)
        )
    if summary.paired_disagreements:
        failures.append(
            "SC-011: paired dictations disagree on "
            + ", ".join(summary.paired_disagreements)
        )
    if (
        summary.parity_gap is not None
        and min(summary.cases.values()) >= PARITY_FLOOR
        and summary.parity_gap > PARITY_GAP_POINTS
    ):
        failures.append(f"SC-005: parity gap {summary.parity_gap} points")
    if summary.errors:
        failures.append("extraction errors: " + "; ".join(summary.errors))
    if baseline is not None:
        for language, accuracy in summary.accuracy.items():
            before = baseline.accuracy.get(language)
            if before is not None and accuracy < before - REGRESSION_TOLERANCE_POINTS:
                failures.append(
                    f"{language} field accuracy regressed: {before} -> {accuracy}"
                )
    return failures


def check_transcription_gates(
    wer: dict[str, float],
    glossary_recall: dict[str, float],
    baseline_wer: dict[str, float] | None,
) -> list[str]:
    """List every transcription gate the run fails.

    Args:
        wer: Word error rate per language, in percent.
        glossary_recall: Glossary recall per language, in percent.
        baseline_wer: The recorded WER baseline, if any.

    Returns:
        One message per failed gate; empty when the run passes.
    """
    failures = [
        f"SC-010: {language} glossary recall {recall}% < {GLOSSARY_RECALL_PERCENT}%"
        for language, recall in glossary_recall.items()
        if recall < GLOSSARY_RECALL_PERCENT
    ]
    if baseline_wer is not None:
        failures.extend(
            f"{language} word error rate regressed: {baseline_wer[language]} -> {rate}"
            for language, rate in wer.items()
            if language in baseline_wer
            and rate > baseline_wer[language] + WER_TOLERANCE_POINTS
        )
    return failures
