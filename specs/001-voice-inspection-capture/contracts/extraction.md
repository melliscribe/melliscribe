# Extraction Contract

The interface between a transcript and an `InspectionRecord`. This is the
contract the eval gate measures (Principle II) and the one Claude is structurally
constrained to.

## Mechanism

`claude-opus-5` via the `anthropic` Python SDK, with `output_config.format`
carrying a JSON Schema **generated from the Pydantic extraction model** — never
hand-written, or the single-source-of-truth chain breaks at its most important
link.

Since schema version 3 the per-field results are **one list of observations**,
each naming its field: a typed object per field produced a grammar too large
for structured outputs (ADR-0003 addendum). An out-of-vocabulary value is read
as unmappable and a missing field as unknown, in
`pipeline/extraction/observations.py`.

Structured outputs mean the response is schema-valid by construction. There is
no JSON-repair path, no prose-stripping, no retry-on-parse-failure. If those
appear in the code, the contract is being worked around rather than used.

## Prompt layout — order is load-bearing

Prompt caching is prefix-match: any byte change invalidates everything after it
(D5). The order below is not stylistic.

```
┌─ system: extraction instructions          ┐
├─ controlled vocabularies, with labels     │  stable prefix
├─ bilingual beekeeping glossary            │  ← cache_control breakpoint
├─ few-shot examples (fr + en)              ┘
└─ the transcript                              ← varies per request
```

Putting the transcript, a timestamp, or a per-request id before the breakpoint
silently drops the cache hit rate to zero on every call, and nothing surfaces it
except the bill. This traces to constitution Principle VI: per-call cost is a
recorded, queryable figure, and a silently invalidated cache makes that figure
quietly wrong for every record. **`usage.cache_read_input_tokens` must be non-zero on the
second and later calls; assert it in a test.**

## Extraction rules the prompt must enforce

**The spec is authoritative.** Every rule below restates a functional
requirement; the prompt implements the spec and is never where a new
requirement is introduced. A behaviour that belongs here but has no FR is a gap
in the spec, and the spec gets amended rather than the rule quietly added.

1. **Never populate an unmentioned field.** Absent means `UNKNOWN` with a null
   value — not a default, not a carry-over from a previous inspection, not a
   plausible guess (FR-007, SC-004: zero tolerance).
2. **Never force a value into the nearest vocabulary member.** Unmappable means
   `UNCERTAIN` with the verbatim phrase retained (FR-006d).
3. **Always return the verbatim phrase** for any populated field, quoted from
   the transcript rather than paraphrased (FR-006b).
4. **Always return the segment reference** the phrase came from, so playback
   lands on the right words (FR-023).
5. **Treatments are never inferred** (FR-014c). A half-heard product name or
   dose is `UNCERTAIN`, never resolved to the nearest known product.
6. **Coded values are language-neutral.** A French transcript and an equivalent
   English one produce identical values (FR-006c, FR-013).
7. **Spoken corrections win** (FR-006f). "Queen seen — no wait, I didn't see
   her, just eggs" resolves to the correction. An unclear correction flags the
   field rather than picking a side.
8. **One hive per record** (FR-015, FR-015e). A transcript covering several
   hives flags the hive field rather than splitting or picking one.
9. **Brood stages and brood pattern are separate fields** (FR-006m). "All
   stages but patchy" sets both; neither is lost to the other.
10. **Frame counts are taken only as said** (FR-006j). Brood, stores and
    bee-covered frame counts are never worked out from a state field, another
    count or a previous inspection.
11. **Counts are reported as spoken** (FR-006j, FR-006k). Faces are reported
    as faces and converted to frames in domain code; a range or hedge is marked
    approximate. Approximate, negative, non-half-step and over-40 counts are
    flagged with no suggested number, and a count contradicting its state field
    flags both (FR-006l) — all applied after extraction, not by the prompt.

## Request shape

| Setting | Value | Why |
|---|---|---|
| `model` | `claude-opus-5` | Not downgraded on a hunch. A cheaper tier is an eval-backed decision, recorded. |
| `output_config.format` | JSON Schema from the Pydantic model | The contract itself |
| `thinking` | adaptive (the default on Opus 5) | Extraction involves genuine ambiguity resolution |
| `cache_control` | after the few-shot block | D5 |
| `max_tokens` | ~16000, non-streaming | Records are small; well clear of the cap |

**Deferred path** (US2): identical request, submitted through the Message
Batches API at 50% cost (D4). `custom_id` is the recording's client-generated
UUID. Results arrive in arbitrary order — key by `custom_id`, never by position.

## Transcription interface

`TranscriptionBackend` is application-owned, so a provider swap never reaches
domain code (constitution Technology Constraints). Provider chosen in ADR-0002.

```
transcribe(audio: bytes, audio_format: str, language: Language) -> Transcript
```

The returned `Transcript` must carry segment-level timestamps. A backend that
cannot supply them cannot satisfy US3 and fails ADR-0002's criterion 3.

## Tracing

Both stages write an `LLMTrace` row (Principle VI, D7): provider, model, prompt
version, token counts, `cache_read_tokens`, computed cost, latency, outcome.
Errors and timeouts are recorded, never swallowed. A fallback path sets
`fallback_taken`.

## What the eval measures

| Check | Criterion | Gate |
|---|---|---|
| Fields populated from unmentioned content | SC-004 | Zero — any occurrence fails the build |
| Confidently-asserted wrong values | SC-003 | Under 15% of all corrections |
| French vs English field accuracy | SC-005 | Gap ≤ 5 points |
| Coded-value agreement across languages | FR-006c | Identical on paired fr/en transcripts |
| Glossary term recall | FR-014, SC-010 | ≥95% per language |
| Uncertainty threshold calibration | FR-008a, SC-003 | Under 15% confident-and-wrong |

No change to a prompt file, model, vocabulary, or extraction schema merges
without this run (Principle II).
