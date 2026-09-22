# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe eval`: the one entry point CI and the maintainer both use.

A local run and the gate cannot diverge because they are the same command.
`compare` prints the before/after table that goes in the pull request
description (Principle II).
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any

from melliscribe.evals.dataset import ExtractionCase
from melliscribe.evals.dataset import TranscriptionCase
from melliscribe.evals.dataset import load_manifest
from melliscribe.evals.gates import check_extraction_gates
from melliscribe.evals.gates import check_transcription_gates
from melliscribe.evals.runner import get_private_storage
from melliscribe.evals.runner import run_extraction
from melliscribe.evals.runner import run_transcription
from melliscribe.evals.scoring import ExtractionSummary
from melliscribe.pipeline.extraction.claude import ClaudeExtractor
from melliscribe.pipeline.extraction.prompts import CURRENT_PROMPT_VERSION
from melliscribe.pipeline.tracing.writer import InMemoryTraceSink
from melliscribe.pipeline.transcription.factory import build_transcription_backend

if TYPE_CHECKING:
    import argparse

EVALS_DIR = Path(__file__).resolve().parents[3] / "evals"
BASELINES_DIR = EVALS_DIR / "baselines"


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register the `eval` subcommands.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("eval", help="run the evaluation gate")
    commands = parser.add_subparsers(dest="eval_command", required=True)

    run_parser = commands.add_parser("run", help="run a dataset and apply the gates")
    run_parser.add_argument("--dataset", required=True, type=Path)
    run_parser.add_argument("--stage", choices=["transcription", "extraction"])
    run_parser.add_argument("--baseline", type=Path, help="default: evals/baselines/")
    run_parser.add_argument("--output", type=Path, help="write the report here")
    run_parser.add_argument("--prompt-version", default=CURRENT_PROMPT_VERSION)
    run_parser.add_argument("--no-cache", action="store_true")
    run_parser.add_argument("--json", action="store_true")
    run_parser.set_defaults(handler=run)

    compare = commands.add_parser("compare", help="before/after table for a PR")
    compare.add_argument("baseline", type=Path)
    compare.add_argument("candidate", type=Path)
    compare.add_argument("--json", action="store_true")
    compare.set_defaults(handler=compare_reports)


def resolve_dataset(path: Path) -> Path:
    """Find a dataset given as a path or relative to `backend/evals/`.

    Args:
        path: The path as given.

    Returns:
        The existing path.

    Raises:
        FileNotFoundError: When the dataset exists in neither place.
    """
    for candidate in (path, EVALS_DIR / path):
        if candidate.is_file():
            return candidate
    msg = f"dataset not found: {path}"
    raise FileNotFoundError(msg)


def default_baseline(dataset: Path, stage: str) -> Path:
    """Return where a dataset's recorded baseline lives.

    Args:
        dataset: The dataset.
        stage: The pipeline stage.

    Returns:
        The baseline path, which may not exist yet.
    """
    return BASELINES_DIR / f"{dataset.stem}.{stage}.json"


def _load_extraction_summary(path: Path) -> ExtractionSummary | None:
    """Load an extraction report's summary.

    Args:
        path: The report file.

    Returns:
        The summary, or None when the file does not exist.
    """
    if not path.is_file():
        return None
    return ExtractionSummary(**json.loads(path.read_text("utf-8"))["summary"])


def _run_extraction_stage(
    args: argparse.Namespace, cases: list[Any], baseline_path: Path
) -> tuple[dict[str, Any], list[str]] | None:
    """Run the extraction cases of a dataset.

    Args:
        args: The parsed arguments.
        cases: Every case of the dataset.
        baseline_path: The recorded baseline.

    Returns:
        The report and failed gates, or None when there are no such cases.

    Raises:
        MissingCredentialsError: When no API key is configured.
    """
    selected = [c for c in cases if isinstance(c, ExtractionCase)]
    if not selected:
        return None
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise MissingCredentialsError
    extractor = ClaudeExtractor(
        InMemoryTraceSink(),
        prompt_version=args.prompt_version,
        use_cache=not args.no_cache,
    )
    report = run_extraction(selected, extractor, get_private_storage())
    failures = check_extraction_gates(
        ExtractionSummary(**report["summary"]), _load_extraction_summary(baseline_path)
    )
    return report, failures


def _run_transcription_stage(
    cases: list[Any], baseline_path: Path
) -> tuple[dict[str, Any], list[str]] | None:
    """Run the transcription cases of a dataset.

    Args:
        cases: Every case of the dataset.
        baseline_path: The recorded baseline.

    Returns:
        The report and failed gates, or None when there are no such cases.
    """
    selected = [c for c in cases if isinstance(c, TranscriptionCase)]
    if not selected:
        return None
    report = run_transcription(
        selected, build_transcription_backend(), get_private_storage()
    )
    baseline_wer = None
    if baseline_path.is_file():
        baseline_wer = json.loads(baseline_path.read_text("utf-8"))["summary"]["wer"]
    failures = check_transcription_gates(
        report["summary"]["wer"], report["summary"]["glossary_recall"], baseline_wer
    )
    return report, failures


class MissingCredentialsError(Exception):
    """Extraction evals need `ANTHROPIC_API_KEY`."""


def run(args: argparse.Namespace) -> int:
    """Run every stage present in the dataset and apply its gates.

    Args:
        args: The parsed arguments.

    Returns:
        0 when every gate passes, 1 when any fails, 3 on missing input.
    """
    dataset = resolve_dataset(args.dataset)
    cases: list[Any] = list(load_manifest(dataset))
    stages = [args.stage] if args.stage else ["extraction", "transcription"]
    reports: list[dict[str, Any]] = []
    failures: list[str] = []
    for stage in stages:
        baseline = args.baseline or default_baseline(dataset, stage)
        try:
            outcome = (
                _run_extraction_stage(args, cases, baseline)
                if stage == "extraction"
                else _run_transcription_stage(cases, baseline)
            )
        except MissingCredentialsError:
            print("error: extraction evals need ANTHROPIC_API_KEY", file=sys.stderr)
            return 3
        if outcome is None:
            continue
        report, stage_failures = outcome
        report |= {"dataset": dataset.name, "prompt_version": args.prompt_version}
        reports.append(report)
        failures += stage_failures
    if args.output:
        payload = reports[0] if len(reports) == 1 else reports
        args.output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    if args.json:
        print(
            json.dumps({"reports": reports, "failures": failures}, ensure_ascii=False)
        )
    else:
        for report in reports:
            summary = json.dumps(report["summary"], ensure_ascii=False)
            print(f"{report['stage']}: {summary}")
        print("PASS" if not failures else "FAIL")
    for failure in failures:
        print(f"gate: {failure}", file=sys.stderr)
    return 1 if failures else 0


def compare_reports(args: argparse.Namespace) -> int:
    """Print the before/after table for two extraction reports.

    Args:
        args: The parsed arguments.

    Returns:
        1 when the candidate fails a gate against the baseline, else 0.
    """
    before = _load_extraction_summary(args.baseline)
    after = _load_extraction_summary(args.candidate)
    if before is None or after is None:
        msg = "both reports must exist"
        raise FileNotFoundError(msg)
    rows: list[tuple[str, Any, Any]] = [("cases", before.cases, after.cases)]
    rows += [
        (f"accuracy {lang}", before.accuracy.get(lang), after.accuracy.get(lang))
        for lang in sorted(set(before.accuracy) | set(after.accuracy))
    ]
    rows += [
        ("parity gap", before.parity_gap, after.parity_gap),
        (
            "SC-004 violations",
            len(before.unmentioned_populated),
            len(after.unmentioned_populated),
        ),
        (
            "SC-011 disagreements",
            len(before.paired_disagreements),
            len(after.paired_disagreements),
        ),
    ]
    failures = check_extraction_gates(after, before)
    if args.json:
        print(json.dumps({"rows": rows, "failures": failures}, ensure_ascii=False))
    else:
        print("| Metric | Baseline | Candidate |\n|---|---|---|")
        for name, old, new in rows:
            print(f"| {name} | {old} | {new} |")
        print("\n**Gate**: " + ("PASS" if not failures else "FAIL"))
        for failure in failures:
            print(f"- {failure}")
    return 1 if failures else 0
