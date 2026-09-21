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
