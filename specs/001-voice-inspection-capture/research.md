# Phase 0 Research: Voice Inspection Capture

**Date**: 2026-09-21 | **Feature**: [spec.md](./spec.md) | **Plan**: [plan.md](./plan.md)

Each decision below that the constitution lists as cross-cutting (Principle VII)
becomes an ADR in `docs/adr/`. This file is the working record; the ADRs are the
durable one.

---

## D1: The pipeline is two providers, not one

**Decision**: Transcription and extraction are separate stages with separate
providers. Speech to text comes from a dedicated ASR service; text to structured
record comes from Claude.

**Rationale**: Claude has no speech-to-text input. This is not a preference — it
settles the architecture. It also happens to be the right shape: the two stages
fail differently, cost differently, and are evaluated differently. A
mis-transcription of "hausse" is an ASR problem; a correct transcript coded into
the wrong temperament value is an extraction problem. Keeping them separate is
what lets the eval set attribute a failure to one or the other.

**Consequence**: Two interfaces, two eval sets, two entries in the trace.

**Alternatives considered**: A single multimodal audio-in call would be one
provider and one prompt, but it cannot be attributed when it goes wrong, and
there is no transcript to show the beekeeper under US3.

---

## D2: ASR provider — deferred to an ADR, with the criteria fixed now

**Decision**: Not chosen in this plan. The pipeline goes behind
`TranscriptionBackend`, an application-owned interface, and the first
implementation is whatever the ADR picks. **ADR-0002 must land before any
transcription task starts.**

**Criteria, in priority order**:

1. **French and English at parity.** SC-005 allows a 5-point gap. An engine that
   is excellent in English and mediocre in French fails this feature outright.
2. **Domain vocabulary steering.** Some mechanism to bias toward the glossary —
   keyword boosting, a custom vocabulary, or an initial prompt. Beekeeping terms
   are exactly what a general model gets wrong, and FR-014 binds accuracy to the
   glossary.
3. **Word-level timestamps.** US3 requires playback to start at the passage a
   field came from. Without timestamps that story cannot be built.
4. **Privacy posture.** Principle III demands the set of services receiving user
   content be documented in user-facing terms, and a documented processor is
   acceptable — but a self-hosted engine removes the disclosure and the egress
   entirely.
5. **Cost per minute at this volume**, which is small: a few dozen recordings of
   a few minutes each per beekeeper per week.

**Candidates to evaluate against a real bilingual sample** (verify current
pricing and capabilities at decision time — do not trust remembered numbers):
self-hosted Whisper-family models such as `faster-whisper`, which removes third
party egress at the cost of running inference, versus hosted APIs from Deepgram,
AssemblyAI, Google, or OpenAI, which remove the ops burden at the cost of
disclosure and per-minute billing.

**Recommendation to carry into the ADR**: start self-hosted if the deployment
already has anywhere to run it, because it satisfies Principle III with no
disclosure surface and no per-minute cost, and because a solo maintainer's
unpredictable usage pattern suits a fixed cost better than a metered one. Switch
to hosted if the French accuracy gap measured on the eval set cannot be closed.

---

## D3: Extraction uses Claude with structured outputs

**Decision**: `claude-opus-5` via the official `anthropic` Python SDK, with
`output_config.format` carrying a JSON Schema generated from the Pydantic v2
extraction model.

**Rationale**: This is the load-bearing decision for Principle IV. The chain is:

```
Pydantic v2 model
   ├──> JSON Schema ──> output_config.format ──> Claude returns conforming JSON
   │                                              └──> validated back into the same model
   └──> OpenAPI schema ──> generated TypeScript types for the frontend
```

One definition of an inspection record drives the LLM contract, the API contract
and the frontend types. Drift between them stops being possible rather than
becoming a thing to remember. Structured outputs also remove the whole class of
"the model returned prose around the JSON" failures that would otherwise need
parsing defences.

**Model**: `claude-opus-5` ($5/MTok input, $25/MTok output, 1M context).
Extraction of a few-minute transcript is a small-input, small-output call, so
per-record cost is dominated by the cached prefix, not the model tier. **Do not
downgrade to `claude-sonnet-5` or `claude-haiku-4-5` on a hunch** — if cost
becomes a real problem, that is a decision to make against the eval set, where
the accuracy delta is measurable, and to record. Thinking stays adaptive
(the default on Opus 5); effort is a tuning knob for later, measured.

**Alternatives considered**: tool-use with `strict: true` gives the same schema
guarantee but adds a tool-call round trip for no benefit when the only output is
the record. Free-form JSON with a parser is what structured outputs exist to
replace.

---

## D4: Deferred processing runs through the Batch API

**Decision**: US2's queued recordings are extracted via the Message Batches API.
Live single-record extraction uses the regular endpoint.

**Rationale**: Batch runs asynchronously at 50% cost, and US2 is by definition
not latency sensitive — a beekeeper who recorded twenty hives in a dead valley
is not watching a spinner. This halves the cost of the bulk path for a
one-line-different call site. SC-007's 5-minute target applies from connectivity
returning, which batch comfortably meets.

**Consequence**: The extraction interface needs both a single and a batch entry
point. Results arrive in arbitrary order and are keyed by `custom_id`, which
maps to the recording's stable client-generated id (FR-020's idempotency key
does double duty here).

---

## D5: Prompt caching on the stable prefix

**Decision**: The extraction prompt is ordered stable-first — system prompt,
controlled vocabularies, bilingual glossary, few-shot examples — with a
`cache_control` breakpoint after it. The transcript, which varies per request,
goes last.

**Rationale**: The vocabularies and glossary are large, identical on every
extraction call, and change only when the project changes them. That is the
textbook cached prefix. Getting the order wrong — putting the transcript or a
timestamp before the glossary — silently invalidates the cache on every call and
nobody notices except the bill.

**Verification**: `usage.cache_read_input_tokens` must be non-zero on the second
and subsequent calls. This belongs in a test, not in a habit.

**Consequence**: Prompt and vocabulary versions become part of the cache key, so
FR-011's provenance recording and the caching strategy share a version number.

---

## D6: Prompts and vocabularies are versioned files

**Decision**: Prompts live in `backend/src/melliscribe/pipeline/extraction/prompts/`
as files with an explicit version identifier. Controlled vocabularies live
alongside them as data. Neither is an inline string literal.

**Rationale**: Constitution Principle II requires this directly. It is also what
makes FR-011 implementable — "which prompt produced this record" has an answer
only if prompts have identities. And it is what makes the eval gate meaningful:
a diff to a prompt file is visible in review, a changed f-string inside a
function is not.

---

## D7: Tracing is a Postgres table, not a platform

**Decision**: Every ASR and Claude call writes a row to a `llm_trace` table:
stage, provider, model, prompt version, input and output tokens, computed cost,
latency, outcome, and the recording id. No third-party observability platform in
this feature.

**Rationale**: Principle VI demands per-call cost and latency and demands they be
queryable in aggregate. A table in the database that already exists satisfies
both, in roughly fifty lines, with no new dependency, no new account and no new
egress of user-adjacent data. Principle V says prefer boring. Langfuse, Phoenix
and OpenTelemetry collectors are all more capable and all more than this needs
at one maintainer and a few dozen recordings a week.

**Consequence**: Cost is computed at call time from a per-model rate table that
must be kept current. A stale rate table produces confidently wrong cost
reporting, which is worse than none — so the rates carry the date they were
checked. Revisit if aggregate queries start needing more than SQL.

**Alternatives considered**: OpenTelemetry with an OTLP backend is the right
answer at a team and a real traffic volume, and the trace-writing call site is
deliberately thin enough to swap later.

---

## D8: Offline storage and sync

**Decision**: IndexedDB for durable local storage, accessed through a thin
wrapper. Audio blobs and a pending-operations queue are separate object stores.
Upload is attempted opportunistically and retried with backoff; Background Sync
is used where available and treated as an optimisation, never as the guarantee.

**Rationale**: FR-002 requires durable persistence before the UI confirms, and
FR-003 forbids dropping local data before server acknowledgement. That is a
queue with explicit state, not a fire-and-forget upload. Background Sync is not
available everywhere and is not reliable enough to be the only path; the
foreground retry is the actual mechanism.

**Conflict resolution**: Not needed in this feature. A recording is written once
by one device and never edited concurrently — FR-006's stable client-generated
id makes the upload idempotent, which is the whole of the sync story here.
Record editing is single-user single-device. **This is why sync conflict
resolution does not get an ADR yet**, despite the constitution listing it: there
is no conflict to resolve until records can be edited from two places.

---

## D9: Audio capture format

**Decision**: `MediaRecorder` producing Opus in a WebM container on the web,
with the native container accepted from Capacitor later. The ASR interface takes
a format-tagged blob and the adapter deals with it.

**Rationale**: Opus is the right codec for speech at low bitrate, which matters
when the file has to survive in IndexedDB on a phone and then upload over a
marginal connection. Browser support for MediaRecorder output formats is not
uniform, so the recorded format is detected and stored rather than assumed.

**Consequence**: FR-005's "existing audio file" path must accept formats the app
did not produce, and FR-005's unsupported-format edge case is real work, not a
theoretical branch.

---

## D10: Evaluation harness

**Decision**: pytest-driven, with datasets as JSONL manifests pointing at audio
held in private storage. Two eval sets, one per pipeline stage. Runs in CI as a
blocking gate on any change to a prompt, model, vocabulary, or extraction schema.

**Rationale**: Principle II requires evals in CI, and Principle V requires
boring. The project already has pytest, CI, and a way to run Python. A dedicated
eval platform is another dependency, another account, and another thing to learn
for a maintainer with a few hours a week.

**Metrics**, mapped to the spec's success criteria:

| Metric | Spec criterion | Gate |
|---|---|---|
| Fields populated that the dictation never mentioned | SC-004 | Zero. Any occurrence fails the build. |
| Corrections of confidently-asserted wrong values | SC-003 | Under 15% of all corrections |
| French vs English field accuracy | SC-005 | Gap ≤ 5 points |
| Transcription word error rate, per language | FR-014 | Baseline recorded; regressions block |
| Glossary term recall | FR-014 | Baseline recorded; regressions block |

**Privacy**: The manifest is versioned; the audio is not. FR-027f means the
dataset is built from purpose-made and explicitly consented recordings, not
harvested from users.

---

## ADRs this feature must produce

Per Principle VII, before the work each one gates begins:

| ADR | Decision | Gates |
|---|---|---|
| ADR-0001 | Two-stage pipeline with application-owned interfaces (D1) | All pipeline work |
| ADR-0002 | ASR provider and deployment model (D2) | Any transcription task |
| ADR-0003 | Claude with structured outputs as the extraction mechanism (D3, D5) | Any extraction task |
| ADR-0004 | Local storage format and the offline upload queue (D8) | Any capture task |
| ADR-0005 | Eval harness and dataset layout (D10) | Any LLM behaviour merging |
| ADR-0006 | Tracing as a database table (D7) | Any pipeline call site |

Authentication is listed as ADR-worthy by the constitution but is out of scope
here — this feature assumes a single authenticated beekeeper and does not build
the authentication model.
