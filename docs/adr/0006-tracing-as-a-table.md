# ADR-0006: LLM tracing as a database table

**Status**: Accepted
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)

## Context

Principle VI requires every LLM call to be traced with model, prompt version,
token counts, computed cost, latency and outcome, and requires traces to be
queryable in aggregate so cost per inspection and latency percentiles are
answerable without instrumenting a one-off script.

The rationale in the constitution is specific: cost and latency are the two
failure modes a side project discovers too late — one by way of a bill, the
other by way of a beekeeper giving up on a spinner in the sun.

There is also a narrower need. ADR-0003 depends on prompt caching working, and a
silently invalidated cache is invisible except in aggregate spend. Something has
to record `cache_read_input_tokens` per call or that dependency is unverifiable
in production.

## Decision

**A `llm_trace` table in the PostgreSQL database that already exists.** Both
pipeline stages write a row.

| Column | Purpose |
|---|---|
| `recording_id`, `stage` | Attribution to a recording and to transcription or extraction |
| `provider`, `model`, `prompt_version` | What produced it |
| `input_tokens`, `output_tokens`, `cache_read_tokens` | Volume, and cache verification |
| `cost_usd` | Computed at call time |
| `latency_ms` | |
| `outcome` | `SUCCESS` / `ERROR` / `TIMEOUT` — errors recorded, never swallowed |
| `fallback_taken` | A silent fallback still emits a trace saying it was taken |

Cost is computed from a **per-model rate table carrying the date it was last
checked**. A stale rate produces confidently wrong cost reporting, which is worse
than no reporting, so the staleness is visible in the data rather than implicit.

Aggregate questions are answered in SQL. No third-party observability platform.

## Consequences

**Good.** Roughly fifty lines, no new dependency, no new account, and no egress
of user-adjacent data — trace rows reference a recording rather than containing
what was said, which keeps them clear of Principle III. Cost per inspection is a
`GROUP BY`. The cache dependency from ADR-0003 becomes checkable in production:
a zero in `cache_read_tokens` after the first call means every call is paying
full price.

**Costly.** The rate table must be maintained by hand, and nothing will remind
anyone. Traces grow with usage and will eventually need a retention policy of
their own, which does not exist yet. Aggregations are hand-written SQL rather
than a dashboard.

**Limited on purpose.** No distributed tracing, no spans, no sampling, no
percentile pre-computation. At one maintainer and a few dozen recordings a week
those are answers to questions nobody is asking.

## Alternatives considered

**OpenTelemetry with an OTLP backend.** The right answer at a team and real
traffic volume, and genuinely better: spans, propagation, an ecosystem. Rejected
for now under Principle V — a collector, a backend and a new vocabulary to buy
per-call figures that one table already provides. **The trace-writing call site
is deliberately thin enough to swap**, and that thinness is the mitigation for
having chosen the smaller option.

**Langfuse or Phoenix.** LLM-native, with prompt-level analytics and eval
integration that would overlap usefully with ADR-0005. Rejected: a hosted
service receiving prompt and completion data is a Principle III question this
feature does not need to open, and a self-hosted one is infrastructure to run.

**Logging to stdout and grepping.** Satisfies "recorded" and fails "queryable in
aggregate". Cost per inspection would be a scripting exercise every time, which
is precisely what the principle forbids.
