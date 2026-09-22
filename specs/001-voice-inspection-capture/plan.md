# Implementation Plan: Voice Inspection Capture

**Branch**: `001-voice-inspection-capture` | **Date**: 2026-09-21 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-voice-inspection-capture/spec.md`

## Summary

A beekeeper dictates a hive inspection; the system returns a structured record
with unknown and uncertain fields flagged rather than guessed.

The technical shape follows from one fact established in Phase 0: Claude has no
speech-to-text, so this is a **two-stage pipeline** — a dedicated ASR provider
turns audio into a timestamped transcript, then Claude turns the transcript into
a record using structured outputs constrained by a JSON Schema generated from
the Pydantic v2 model. That same Pydantic model generates the OpenAPI schema
that generates the frontend's TypeScript types, so one definition drives the LLM
contract, the API contract and the client types.

Capture is offline-first and interpretation is not: the phone durably stores a
recording with no network, and the record is produced when connectivity returns.
Queued recordings extract through the Batch API at half cost.

## Technical Context

**Language/Version**: Python 3.13 (backend), TypeScript 5.x (frontend)

**Primary Dependencies**: FastAPI, Pydantic v2, SQLAlchemy + Alembic,
`anthropic` SDK, React, Vite, `openapi-typescript`. ASR client library is
deferred to ADR-0002.

**Storage**: PostgreSQL (system of record); IndexedDB (device-durable capture
queue); object storage for audio blobs

**Testing**: pytest with snapshot-based exception assertions, Vitest, Playwright
for the gloved-hands and offline flows, plus the eval harness as a separate
blocking CI job

**Target Platform**: PWA in mobile browsers (primary), Linux server backend.
Capacitor shell deferred — see Complexity Tracking.

**Project Type**: Web application — Python backend, React PWA frontend

**Performance Goals**: Record available within 5 minutes of connectivity
returning (SC-007); full dictate-and-confirm cycle inside 90 seconds of the
beekeeper's attention (SC-001). Neither is a server latency target — the
constraint is human, and the pipeline is asynchronous.

**Constraints**: Capture must complete with zero network (Principle I). Every
LLM call traced with cost and latency (Principle VI). French/English parity
within 5 points (SC-005). Zero fields populated from unmentioned content
(SC-004).

**Scale/Scope**: One maintainer, a few hours a week. Single beekeeper per
account, tens of hives, a few dozen recordings of a few minutes per week. This
is small-data; nothing here needs to scale, and designing as though it does
would violate Principle V.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

Evaluated against constitution v2.1.0.

| Principle | Gate | Verdict |
|---|---|---|
| **I. Field-First** | Capture succeeds offline; voice is the primary path; gloved targets; review deferrable | **PASS** — FR-001–004 and FR-024. The US1 contradiction was resolved in clarification: offline guarantees durable capture, not a finished record. |
| **II. Evaluation Before Features** | Eval dataset and CI evals ship with the behaviour, in the same PR | **PASS with ordering constraint** — the eval harness (ADR-0005) and both datasets must exist before any extraction or transcription task merges. This inverts the intuitive build order and is a real scheduling cost. |
| **III. Privacy By Default** | No user audio in the repo; disclosed processors only; retention and deletion | **PASS** — FR-027a–f. Eval datasets are manifests in the repo pointing at audio in private storage. ADR-0002 must state the disclosure if a hosted ASR is chosen. |
| **IV. Single Source Of Truth** | Pydantic v2 authoritative; TS generated from OpenAPI; CI fails on drift | **PASS, strongly** — the same model generates the LLM output schema, the API schema and the client types. See the chain in research.md D3. |
| **V. Simplicity** | Each increment field-usable; no speculative abstraction; boring tech | **PASS with one deferral** — see Complexity Tracking. |
| **VI. Observability** | Every LLM call traced with cost and latency | **PASS** — a `llm_trace` table, written by both pipeline stages (D7). |
| **VII. ADRs** | Cross-cutting decisions recorded in `docs/adr/` | **PASS** — six ADRs identified, each gating the work it covers. |
| **VIII. Bilingual By Construction** | Both languages, coded values language-neutral, evals cover both | **PASS** — FR-006c makes vocabulary values language-neutral identifiers; SC-005 gates parity; the language is an account setting, never a per-recording prompt. |

**No unjustified violations.** The one deferral is recorded below.

### Post-Design Re-check

Re-evaluated after Phase 1. No gate changed verdict. Two design outcomes
strengthen the original assessment:

- The Pydantic-to-everything chain (Principle IV) turned out to be the spine of
  the design rather than a compliance obligation — the extraction contract and
  the client types are the same artifact, so drift is structurally impossible
  rather than merely tested for.
- Tracing (Principle VI) lands as one table written from two call sites, which
  is small enough that it does not compete with Principle V.

One risk surfaced during design and is not a violation but is worth naming: the
eval-before-features ordering (Principle II) means the first several weeks of
work produce no user-visible progress. For a solo maintainer with a few hours a
week, that is the most likely point of abandonment. The task breakdown should
front-load a thin end-to-end path with a tiny eval set rather than a complete
eval suite before any pipeline code.

## Project Structure

### Documentation (this feature)

```text
specs/001-voice-inspection-capture/
├── plan.md              # This file
├── research.md          # Phase 0 output — 10 decisions, 6 ADRs identified
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── README.md
│   ├── api.md           # HTTP surface
│   ├── extraction.md    # The LLM contract
│   └── cli.md           # Library CLIs (Code Standards)
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 — created by /speckit-tasks, not here
```

### Source Code (repository root)

```text
backend/
├── src/melliscribe/
│   ├── models/                  # Pydantic v2 — the single source of truth
│   │   ├── inspection.py        # InspectionRecord, ObservationField
│   │   ├── recording.py
│   │   ├── hive.py
│   │   └── vocabulary.py
│   ├── domain/                  # pure, independently testable libraries
│   │   ├── inspection/          # record assembly, field status rules
│   │   ├── vocabulary/          # controlled vocabularies, bilingual glossary
│   │   └── retention/           # expiry, deletion, warning windows
│   ├── pipeline/
│   │   ├── transcription/       # TranscriptionBackend + adapters (ADR-0002)
│   │   ├── extraction/          # Claude structured output
│   │   │   └── prompts/         # versioned prompt files (D6)
│   │   └── tracing/             # llm_trace writer (D7)
│   ├── api/                     # FastAPI routers — thin adapters only
│   ├── cli/                     # one CLI per domain library
│   └── db/                      # SQLAlchemy models, Alembic migrations
├── evals/
│   ├── harness/                 # pytest-driven runner
│   └── datasets/                # JSONL manifests; audio lives in private storage
└── tests/
    ├── contract/
    ├── integration/
    └── unit/

frontend/
├── src/
│   ├── capture/                 # MediaRecorder, gloved-hands controls
│   ├── review/                  # field review, correction, confirmation
│   ├── offline/                 # IndexedDB stores, upload queue, retry
│   ├── i18n/                    # fr/en catalogues; CI fails on a missing key
│   └── api/generated/           # openapi-typescript output — never hand-edited
└── tests/

docs/adr/                        # ADR-0001 … ADR-0006
```

**Structure Decision**: Web application layout, because the feature genuinely
has a backend and a frontend with different languages and deployment lifecycles.
Domain logic lives in `backend/src/melliscribe/domain/` as libraries with CLIs,
per the constitution's Code Standards — `api/` holds routers that call them and
nothing more. `frontend/src/api/generated/` is build output committed for drift
detection, and CI regenerates it to prove it matches the current schema.

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| Capacitor native shell deferred to a later feature, not built here | The constitution fixes Capacitor as the mobile baseline, so not building it now is a deviation from the stated stack | Not rejected — *chosen*. A PWA is usable in the field today, and the native shell adds app-store process, signing, and two more platforms to test for a maintainer with a few hours a week. Principle V's "each increment usable in the field" is satisfied without it. Revisit when a capability the PWA cannot provide is actually needed. |

No other deviations. The two-stage pipeline is not added complexity — it is
forced by Claude having no audio input, and each stage is separately evaluable,
which the merged alternative would not be.

## Implementation Notes

Divergences from this plan, written back per the constitution's workflow rule.

- **Eval harness location**: `backend/src/melliscribe/evals/` rather than
  `backend/evals/harness/`, so the packaged `melliscribe eval` command can
  import it. Datasets and baselines stay in `backend/evals/`.
- **Structured outputs**: the JSON Schema passed as `output_config.format` is
  `anthropic.transform_schema(ExtractionOutput)` — generated from Pydantic, with
  the SDK moving unsupported constraints into descriptions.
- **Extraction output vs record**: Claude returns an `ExtractionOutput` (what
  was heard, with confidences); statuses, the threshold, hive matching and
  dates are applied in `domain/inspection/`, so they are versioned and tested
  independently of the model.
- **Flat observation list (schema v3)**: a typed object per field exceeded the
  structured-output grammar limit on the first live run. Observations are one
  list naming their field; `pipeline/extraction/observations.py` restores the
  per-field view and rejects out-of-vocabulary values (ADR-0003 addendum).
- **Refusal fallback**: live extraction sends `fallbacks: "default"` (beta
  `server-side-fallback-2026-07-01`); the serving model is recorded in
  provenance and a fallback sets `fallback_taken` on the trace. Batches do not
  support it.
- **Batch deadline**: most batches finish within an hour, which D4's claim
  that batch "comfortably meets" SC-007 does not account for. Batch extraction
  therefore has a 4-minute deadline, after which it is cancelled and the
  remainder extracted live, traced as a fallback.
- **Time zones**: timestamps are stored in UTC and read back timezone-aware on
  both SQLite and PostgreSQL; the capture day is the device's local day.
- **Background Sync** is not wired: the foreground retry is the guarantee
  (ADR-0004), and nothing yet needs the optimisation.
