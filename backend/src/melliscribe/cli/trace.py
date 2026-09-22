# Copyright (C) 2026 Jean-Christophe Giret
# SPDX-License-Identifier: AGPL-3.0-or-later
"""`melliscribe trace`: cost and latency in aggregate, without a one-off script.

Principle VI requires traces to answer "what does an inspection cost" and "how
slow is the pipeline" directly. This is quickstart scenario 9 as a command.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import TYPE_CHECKING
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy.orm import Session

from melliscribe.db.session import get_database_url
from melliscribe.db.tables import LLMTraceRow

if TYPE_CHECKING:
    import argparse
    from collections.abc import Sequence


def add_parser(subparsers: Any) -> None:  # noqa: ANN401 - argparse's private type
    """Register `trace`.

    Args:
        subparsers: The top-level subparsers action.
    """
    parser = subparsers.add_parser("trace", help="aggregate pipeline traces")
    commands = parser.add_subparsers(dest="trace_command", required=True)
    summary = commands.add_parser("summary", help="cost and latency by stage")
    summary.add_argument("--days", type=int, default=30)
    summary.add_argument("--json", action="store_true")
    summary.set_defaults(handler=run_summary)


def percentile(values: Sequence[int], fraction: float) -> int | None:
    """Return a nearest-rank percentile.

    Args:
        values: The samples.
        fraction: The percentile, between 0 and 1.

    Returns:
        The percentile, or None without samples.
    """
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, max(0, round(fraction * len(ordered)) - 1))]


def summarise(rows: Sequence[LLMTraceRow]) -> dict[str, Any]:
    """Aggregate trace rows.

    Args:
        rows: The trace rows.

    Returns:
        Per stage and model: calls, outcomes, latency p50/p95, cost, cache
        reads; cost per inspection; and any rate used without a checked date.
    """
    groups: dict[tuple[str, str], list[LLMTraceRow]] = defaultdict(list)
    per_recording: dict[str, Decimal] = defaultdict(Decimal)
    for row in rows:
        groups[(row.stage, row.model)].append(row)
        per_recording[str(row.recording_id)] += row.cost_usd
    stages = [
        {
            "stage": stage,
            "model": model,
            "calls": len(items),
            "errors": sum(r.outcome == "error" for r in items),
            "timeouts": sum(r.outcome == "timeout" for r in items),
            "fallbacks": sum(r.fallback_taken for r in items),
            "latency_p50_ms": percentile([r.latency_ms for r in items], 0.5),
            "latency_p95_ms": percentile([r.latency_ms for r in items], 0.95),
            "cost_usd": str(sum((r.cost_usd for r in items), Decimal(0))),
            "cache_read_tokens": sum(r.cache_read_tokens or 0 for r in items),
        }
        for (stage, model), items in sorted(groups.items())
    ]
    total = sum(per_recording.values(), Decimal(0))
    return {
        "stages": stages,
        "recordings": len(per_recording),
        "cost_per_recording_usd": str(total / len(per_recording))
        if per_recording
        else None,
        "unpriced_models": sorted(
            {r.model for r in rows if r.rates_checked_on is None and r.model != "none"}
        ),
    }


def run_summary(args: argparse.Namespace) -> int:
    """Print the aggregate.

    Args:
        args: The parsed arguments.

    Returns:
        The exit code.
    """
    since = datetime.now(UTC) - timedelta(days=args.days)
    with Session(create_engine(get_database_url())) as session:
        rows = list(
            session.scalars(select(LLMTraceRow).where(LLMTraceRow.created_at >= since))
        )
    summary = summarise(rows)
    if args.json:
        print(json.dumps(summary))
        return 0
    for stage in summary["stages"]:
        print(
            f"{stage['stage']:13} {stage['model']:20} calls={stage['calls']} "
            f"errors={stage['errors']} p50={stage['latency_p50_ms']}ms "
            f"p95={stage['latency_p95_ms']}ms cost=${stage['cost_usd']} "
            f"cache_read={stage['cache_read_tokens']}"
        )
    print(f"cost per recording: ${summary['cost_per_recording_usd']}")
    if summary["unpriced_models"]:
        print(f"no rate on file for: {', '.join(summary['unpriced_models'])}")
    return 0
