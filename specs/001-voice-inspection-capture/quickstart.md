# Quickstart: Validating Voice Inspection Capture

**Plan**: [plan.md](./plan.md) | **Contracts**: [contracts/](./contracts/)

How to prove the feature works end to end. Scenarios map to the spec's
acceptance criteria; details live in the contracts and data model rather than
being restated here.

## Prerequisites

- Python 3.13, `uv`, Node 20+, PostgreSQL running
- `ANTHROPIC_API_KEY` set, or an active profile from `ant auth login`
- ASR backend configured per ADR-0002
- A bilingual eval dataset manifest, with its audio in private storage

## Setup

```bash
uv sync --project backend
uv run --project backend alembic upgrade head
npm --prefix frontend ci
npm --prefix frontend run generate:api    # OpenAPI -> TypeScript
```

`generate:api` must produce no diff against the committed types. A diff means
the schema moved without the client following, which is the Principle IV gate.

## Scenario 1 — The pipeline, without the app

The fastest proof that extraction works, and the one to reach for when a
beekeeper reports a wrong record.

```bash
uv run --project backend melliscribe pipeline sample-fr.webm --language fr --json
```

**Expect**: a record whose mentioned fields are populated with a coded value,
a verbatim phrase and a segment reference; whose unmentioned fields are
`UNKNOWN` with a null value; and whose ambiguous fields are `UNCERTAIN`.

**Fails the feature if**: any field the audio never mentioned comes back
populated. That is SC-004, and it has zero tolerance.

## Scenario 2 — Offline capture (US1, the core promise)

1. Load the PWA on a phone, put it in airplane mode.
2. Record a dictation naming a hive, the queen, brood, stores and temperament.
3. Stop recording.

**Expect**: an explicit confirmation that the recording is safely stored, with
no network at any point. `GET /recordings` (once online) shows it, and the
IndexedDB queue held it in `PENDING_UPLOAD` throughout.

**Expect after restoring connectivity**: the recording uploads, a record is
produced, and it is reviewable — SC-007 gives this 5 minutes.

**Fails the feature if**: the UI confirmed success before the audio was durably
written (FR-002), or the local copy was dropped before a `201`/`200` (FR-003).

## Scenario 3 — Gloved review

Attempt the review flow wearing beekeeping gloves, outdoors, in sunlight.
Confirm and correct fields without removing them.

**Expect**: every control reachable; no hover-dependent or long-press-only
action on the path; corrections stick. SC-006 wants 90% of beekeepers through
this unassisted.

## Scenario 4 — Bilingual parity (US1, Principle VIII)

```bash
uv run --project backend melliscribe eval run --dataset datasets/parity.jsonl
```

**Expect**: French field accuracy within 5 points of English (SC-005), and
identical coded values on paired fr/en transcripts of the same inspection.

Then, in the app: set the account language to French, start a recording.

**Expect**: no language choice is presented at recording time (FR-026a).

## Scenario 5 — Deferred processing (US2)

Capture several recordings offline, restore connectivity.

**Expect**: each produces its own record, none skipped or merged (US2 scenario
2). Submit the same file twice — **expect one record, not two** (FR-020).

Force a failure (invalid audio): **expect** the recording intact and
retrievable, the failure visible, and `POST /recordings/{id}/retry` recovering
it without re-recording.

## Scenario 6 — Playback (US3)

Open a populated field and play it back.

**Expect**: audio starts at the passage the phrase was taken from, not at the
beginning of the recording.

## Scenario 7 — Retention (US4)

```bash
uv run --project backend melliscribe retention due --within-days 30 --json
```

Then delete a recording whose record exists.

**Expect**: `204`; the record and transcript fully intact; every field still
showing its verbatim phrase; playback reporting *"no longer kept"* rather than
failing silently (FR-027d). `GET /recordings/{id}/audio` returns `410`.

## Scenario 8 — Wrong language, corrected (US1 scenario 6)

Record with the account language set to the wrong one. Confirm a field on the
resulting nonsense record. Correct the language at review and re-process.

**Expect**: a sane record, **with the confirmed field preserved** (FR-026c).
This is the easiest invariant to break during re-processing and the one most
likely to be noticed only by a beekeeper losing work.

## Scenario 9 — Observability (Principle VI)

```sql
SELECT stage, model, count(*), avg(latency_ms), sum(cost_usd),
       sum(cache_read_tokens)
FROM llm_trace GROUP BY stage, model;
```

**Expect**: a row per pipeline stage per call, with non-zero
`cache_read_tokens` after the first extraction — a zero there means the prompt
prefix is being invalidated and every call is paying full price (D5).

## CI gates

All blocking, per the constitution:

```bash
uv run --project backend ruff check . && uv run --project backend ruff format --check .
uv run --project backend ty check
uv run --project backend pytest
npm --prefix frontend run generate:api && git diff --exit-code frontend/src/api/generated
uv run --project backend melliscribe vocabulary check
uv run --project backend melliscribe eval run --dataset datasets/ci.jsonl
```

The last three are this feature's additions: generated-type drift (Principle
IV), translation completeness (Principle VIII), and the eval gate (Principle
II). Any change to a prompt, model, vocabulary or extraction schema requires the
eval result in the pull request description.
