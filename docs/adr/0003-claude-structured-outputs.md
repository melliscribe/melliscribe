# ADR-0003: Claude with structured outputs for extraction

**Status**: Accepted
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)
**Depends on**: [ADR-0001](./0001-two-stage-pipeline.md)

## Context

The extraction stage turns a transcript into an `InspectionRecord`: coded values
from controlled vocabularies, each with a status, a verbatim phrase and a pointer
into the audio. The hard part is not producing JSON — it is producing JSON that
is *structurally guaranteed* to match the record model, because the model carries
the invariant that matters most. SC-004 has zero tolerance: no field may ever be
populated from something the dictation did not mention.

Principle IV requires one authoritative definition of the data. There are three
places an inspection record's shape could drift: the schema the model is asked to
produce, the schema the API serves, and the types the frontend holds.

## Decision

`claude-opus-5` via the official `anthropic` Python SDK, with
`output_config.format` carrying a **JSON Schema generated from the Pydantic v2
extraction model** — never hand-written.

That generation is the whole point:

```
Pydantic v2 model
   ├──> JSON Schema ──> output_config.format ──> Claude's constrained output
   ├──> OpenAPI ──> openapi-typescript ──> frontend types
   └──> the CLI's --json shape
```

One definition, three consumers. Drift between the extraction contract, the API
contract and the client types stops being possible rather than becoming a thing
to remember. CI fails if the committed generated types differ from what the
current schema produces.

Supporting decisions:

- **Prompt caching** on a stable prefix — system instructions, controlled
  vocabularies, glossary, few-shot examples — with the transcript last. Prefix
  ordering is load-bearing: anything volatile before the breakpoint silently
  drops the hit rate to zero on every call and surfaces only on the bill.
  `usage.cache_read_input_tokens` is asserted in a test, not assumed.
- **Batch API for deferred processing.** Queued recordings (US2) extract at 50%
  cost, keyed by the recording's client-generated UUID as `custom_id`. Results
  arrive in arbitrary order.
- **Adaptive thinking**, the default on Opus 5. Extraction involves genuine
  ambiguity resolution — a hedged observation, a spoken self-correction — which
  is what thinking is for.
- **Prompts are versioned files**, not inline literals, so a change is visible
  in review and a record's provenance can name what produced it (FR-011).

## Consequences

**Good.** No JSON-repair path, no prose-stripping, no retry-on-parse-failure. If
those appear in the code, the contract is being worked around rather than used.
The Pydantic model becomes the place to enforce invariants — an `UNKNOWN` field
carrying a value is unrepresentable, which is a cheaper guarantee of SC-004 than
an eval.

**Costly.** Every extraction is a paid API call with a per-record cost, and the
cost is only knowable by measuring (ADR-0006). A vendor dependency on the
extraction path, mitigated by the interface from ADR-0001 but not eliminated.

**Constrained.** Changing the extraction schema changes the LLM contract, the API
contract and the client types at once. That is the intent, and it means schema
changes are never small — they ship with the migration, the regenerated types,
tests for both, and an eval run.

## Model choice

`claude-opus-5` — $5/MTok input, $25/MTok output, 1M context. Extraction is a
small-input, small-output call against a large cached prefix, so per-record cost
is dominated by the cache, not the model tier.

**Not downgraded to `claude-sonnet-5` or `claude-haiku-4-5`.** If cost becomes a
real problem that is a decision to make against the eval set, where the accuracy
delta is measurable, and to record as a superseding ADR. Downgrading on a hunch
trades an unmeasured amount of the one quality this feature is built around for
an unmeasured saving.

## Alternatives considered

**Tool use with `strict: true`.** Gives the same schema guarantee. Rejected: it
adds a tool-call round trip for no benefit when the only output is the record.

**Free-form JSON with a parser and retries.** What structured outputs exist to
replace. Every retry is a paid call and a latency multiplier, and the failure
mode is silent partial extraction.

**A smaller model with a larger prompt.** Deferred, not rejected — it is a valid
future optimisation, and the eval set is what makes it decidable.

## Addendum — 2026-09-23: grammar size, and what an extraction costs

Appended, not edited: the decision stands; two of its assumptions met reality.

**The typed schema did not compile.** The first live run returned
`400 — The compiled grammar is too large` for every request. Structured outputs
compile each distinct object type in the schema, and a typed object per field —
five vocabulary fields plus three frame counts, each with its own value type —
exceeded the limit (bisected: about nine such objects fit). The extraction
schema is now **version 3**: one `Observation` type, in a list, naming its
field. It compiles once and is half the size (6.7 KB). The schema no longer
restricts a value to its field's vocabulary or forces every field to be
addressed; `pipeline/extraction/observations.py` closes both gaps in code,
always on the safe side — an out-of-vocabulary value is unmappable, a missing
field is unknown. The single-source-of-truth chain is unchanged: the schema is
still generated from Pydantic.

**Consequence to watch**: adding fields adds entries to one enum, not new
object types, so the schema should stay well under the limit. A new *kind* of
field (not a vocabulary value, not a count) is a new object type and should be
checked against the API before it merges.

**First smoke eval (10 synthetic cases, 5 fr/en pairs, prompt v3)**: field
accuracy 100% in both languages, no SC-004 violation, no paired disagreement.
Total cost $0.21 — $0.021 per record — with 79,902 cache-read tokens over the
nine calls after the first. Latency p50 5.4 s, p95 8.1 s.

**"Per-record cost is dominated by the cache" — measured: no** (closes T129 and
checklist item CHK043). Derived from that run: cache reads $0.040, the first
call's cache write about $0.056, and about $0.11 of output tokens including
thinking. In steady state a record costs about $0.016, of which the cached
prefix is about a quarter; **output dominates**. So the lever, if cost ever
matters, is effort or output length measured against the eval set — not the
model tier alone, and not the prefix. The trace summary now records input and
output token totals so the next run gives this breakdown directly.
