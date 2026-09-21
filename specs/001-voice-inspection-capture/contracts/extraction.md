# Extraction Contract

The interface between a transcript and an `InspectionRecord`. This is the
contract the eval gate measures (Principle II) and the one Claude is structurally
constrained to.

## Mechanism

`claude-opus-5` via the `anthropic` Python SDK, with `output_config.format`
carrying a JSON Schema **generated from the Pydantic extraction model** — never
hand-written, or the single-source-of-truth chain breaks at its most important
link.

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
except the bill. **`usage.cache_read_input_tokens` must be non-zero on the
second and later calls; assert it in a test.**

## Extraction rules the prompt must enforce

These restate spec requirements that the schema alone cannot express:

1. **Never populate an unmentioned field.** Absent means `UNKNOWN` with a null
   value — not a default, not a carry-over from a previous inspection, not a
   plausible guess (FR-007, SC-004: zero tolerance).
2. **Never force a value into the nearest vocabulary member.** Unmappable means
   `UNCERTAIN` with the verbatim phrase retained (FR-006d).
3. **Always return the verbatim phrase** for any populated field, quoted from
   the transcript rather than paraphrased (FR-006b).
4. **Always return the segment reference** the phrase came from, so playback
   lands on the right words (FR-023).
5. **Treatments are never inferred.** A half-heard product name is `UNCERTAIN`.
6. **Coded values are language-neutral.** A French transcript and an equivalent
   English one produce identical values (FR-006c, FR-013).
7. **Spoken corrections win.** "Queen seen — no wait, I didn't see her, just
   eggs" resolves to the correction, not the first statement.
8. **One hive per record.** A transcript covering several hives flags the hive
   field rather than splitting or picking one.

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
| Glossary term recall | FR-014 | Baseline recorded; regressions block |

No change to a prompt file, model, vocabulary, or extraction schema merges
without this run (Principle II).
