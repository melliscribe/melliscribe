# Tasks: Voice Inspection Capture

**Input**: Design documents from `/specs/001-voice-inspection-capture/`

**Prerequisites**: [plan.md](./plan.md), [spec.md](./spec.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/)

**Tests**: Test tasks are included and are **not optional**. Constitution v2.1.0
makes test-first binding: tests are written before the implementation, observed
to fail, and only then made to pass. Library contracts, API contracts,
offline-to-online sync paths and migrations MUST have tests before the code
exists.

**Organization**: Tasks are grouped by user story so each story can be
implemented, tested and delivered independently.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- Exact file paths are included in every task

## Path Conventions

Web application layout per plan.md: `backend/src/melliscribe/`,
`frontend/src/`, `docs/adr/`.

## ⚠️ Read this before starting

ADR-0005 names the biggest risk in this feature: the evaluation gate means the
first stretch of work produces nothing a beekeeper can see, and for a solo
maintainer with a few hours a week that is the most likely point of abandonment.

**These tasks are ordered to mitigate that.** Phase 2 builds a *minimal* eval
harness with a six-recording smoke dataset — enough to satisfy the gate on a
thin path — and the full 50-per-language dataset grows during Phase 3 as a
condition of closing US1. Do not build the complete eval suite before any
pipeline code exists.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization. Nothing here is feature-specific.

- [ ] T001 Create the backend and frontend directory skeleton per plan.md, including `backend/src/melliscribe/`, `backend/tests/`, `backend/evals/`, `frontend/src/`, `frontend/tests/`
- [ ] T002 Initialize the Python project with `uv` in `backend/pyproject.toml`, declaring FastAPI, Pydantic v2, SQLAlchemy, Alembic, the `anthropic` SDK, pytest and syrupy
- [ ] T003 [P] Configure `backend/.ruff.toml` with `force-single-line = true`, the Google docstring convention, and Pydantic base classes listed under `[lint.flake8-type-checking].runtime-evaluated-base-classes`
- [ ] T004 [P] Configure the type checker in `backend/pyproject.toml` to run with zero unjustified suppressions
- [ ] T005 [P] Initialize the React + TypeScript + Vite PWA in `frontend/package.json` with `strict` mode in `frontend/tsconfig.json`
- [ ] T006 [P] Create `.pre-commit-config.yaml` at the repository root with commitizen for Conventional Commits and a license-header inserter
- [ ] T007 Create `backend/tests/conftest.py` importing the shared gemseo pytest fixtures (`from gemseo.utils.testing.pytest_conftest import *`) for `tmp_wd` and `reset_factory`
- [ ] T008 Create the CI workflow at `.github/workflows/ci.yml` running ruff lint, ruff format check, the type checker and pytest as blocking jobs

**Checkpoint**: `uv run --project backend pytest` runs green on an empty suite; `npm --prefix frontend run build` succeeds.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The single-source-of-truth chain, the vocabularies, the interfaces and a minimal eval gate. Every user story depends on this.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

### The ADR that gates transcription

- [ ] T009 Record 10 bilingual dictations containing real domain vocabulary (`hausse`, `cadre`, `essaimage`, `couvain` and their English equivalents), store them in private storage, and register them in `backend/evals/datasets/smoke.jsonl` — never in the repository (Principle III)
- [ ] T010 Run each ADR-0002 candidate against those recordings measuring word error rate per language, glossary term recall and whether usable segment timings come back; record the figures in `docs/adr/0002-asr-provider.md`
- [ ] T011 Complete the Decision section of `docs/adr/0002-asr-provider.md` and set its status to Accepted — **this unblocks every transcription task**

### Controlled vocabularies and glossary (FR-006g, blocks all extraction)

- [ ] T012 Define the controlled vocabulary for each observation field in `backend/src/melliscribe/models/vocabulary.py` as `StrEnum` classes with CAPITAL_CASED member keys, stating for each field its permitted values, the criteria for membership, and that values are unordered per the spec's Assumptions (FR-006g)
- [ ] T013 [P] Create the bilingual domain glossary at `backend/src/melliscribe/domain/vocabulary/glossary.py` holding both language forms of every term, with a named owner recorded in the module docstring (FR-014a)
- [ ] T014 [P] Add French and English display labels for every vocabulary value to `frontend/src/i18n/fr.json` and `frontend/src/i18n/en.json`, keyed by the language-neutral identifier (FR-006c, FR-006i)
- [ ] T015 Write a failing test in `backend/tests/unit/test_vocabulary_completeness.py` asserting every vocabulary value has a label in both languages, then implement `melliscribe vocabulary check` in `backend/src/melliscribe/cli/vocabulary.py` to exit non-zero on a gap (FR-006i)
- [ ] T016 Add `melliscribe vocabulary check` to `.github/workflows/ci.yml` as a blocking job (Principle VIII)

### Pydantic models — the single source of truth (Principle IV)

- [ ] T017 Create `FieldStatus` in `backend/src/melliscribe/models/inspection.py` with members `UNKNOWN`, `UNCERTAIN`, `SYSTEM_DERIVED`, `CONFIRMED`
- [ ] T018 Write a failing test in `backend/tests/unit/test_observation_field.py` asserting that an `ObservationField` with status `UNKNOWN` and a non-None value is unrepresentable — this is SC-004's zero-tolerance criterion enforced by a validator rather than an eval
- [ ] T019 Implement the generic `ObservationField` in `backend/src/melliscribe/models/inspection.py` carrying `status`, `value` (None unless `SYSTEM_DERIVED` or `CONFIRMED`), `verbatim` (every contributing phrase when a value spans non-contiguous parts, per FR-006b), `segment_ref` and `confidence`, with the validator from T018
- [ ] T020 [P] Implement `Recording` in `backend/src/melliscribe/models/recording.py` with a client-generated `id`, `captured_at`, `duration_seconds`, `language`, `audio_format`, `state`, `retention_expires_at` (nullable), `audio_available` and `failure_reason` (nullable)
- [ ] T021 [P] Implement `RecordingState` in `backend/src/melliscribe/models/recording.py` with `PENDING_UPLOAD`, `UPLOADED`, `TRANSCRIBING`, `EXTRACTING`, `PROCESSED`, `FAILED`
- [ ] T022 [P] Implement `Transcript` and `TranscriptSegment` in `backend/src/melliscribe/models/transcript.py`, segments ordered and non-overlapping, each with `text`, `start_seconds`, `end_seconds`, `confidence`
- [ ] T023 [P] Implement `Hive` in `backend/src/melliscribe/models/hive.py` with `identifier` non-empty and trimmed, unique per account (FR-015d)
- [ ] T024 [P] Implement `Treatment` and `ActionToDo` in `backend/src/melliscribe/models/inspection.py` — treatment `product` and `dose` as `ObservationField[str]` always stored as spoken with no controlled vocabulary (FR-014c), `ActionToDo.text` as free text
- [ ] T025 [P] Implement `Provenance` in `backend/src/melliscribe/models/provenance.py` with `transcription_provider`, `transcription_model`, `extraction_model`, `prompt_version`, `vocabulary_version`, `extraction_schema_version`, `uncertainty_threshold` (FR-008a) and `extracted_at`
- [ ] T026 Implement `InspectionRecord` in `backend/src/melliscribe/models/inspection.py` composing the observation fields, `hive_id` (nullable while unresolved), `inspection_date`, `treatments`, `actions_to_do`, `confirmed_at` (nullable — unconfirmed is a valid saved state per FR-024) and `provenance`
- [ ] T027 Write a failing test in `backend/tests/unit/test_vocabulary_supersede.py` asserting a vocabulary value used by an existing record cannot be removed or redefined, then implement the supersede mechanism in `backend/src/melliscribe/models/vocabulary.py` (FR-006h)

### Database and migrations

- [ ] T028 Configure Alembic in `backend/alembic.ini` and `backend/src/melliscribe/db/migrations/`
- [ ] T029 Write a forward migration test in `backend/tests/integration/test_migrations.py` that runs every migration against a seeded database, then create the initial migration for hives, recordings, transcripts, records, observation fields, treatments and actions
- [ ] T030 Create the account settings table and model in `backend/src/melliscribe/models/account.py` with `language` and `audio_retention_days` defaulting to 365 (FR-027a)

### Generated types and the drift gate (Principle IV)

- [ ] T031 Configure FastAPI in `backend/src/melliscribe/api/app.py` to emit an OpenAPI schema from the Pydantic models
- [ ] T032 Add an `openapi-typescript` script to `frontend/package.json` generating `frontend/src/api/generated/` from that schema
- [ ] T033 Add a blocking CI job to `.github/workflows/ci.yml` that regenerates the types and fails on any diff against the committed output

### Pipeline interfaces and tracing (ADR-0001, ADR-0006)

- [ ] T034 Define the `TranscriptionBackend` protocol in `backend/src/melliscribe/pipeline/transcription/base.py` as `transcribe(audio, audio_format, language) -> Transcript`, requiring segment-level timestamps
- [ ] T035 [P] Define the `Extractor` protocol in `backend/src/melliscribe/pipeline/extraction/base.py` taking a `Transcript` and returning an `InspectionRecord`
- [ ] T036 Create the `llm_trace` table migration and the `LLMTrace` model in `backend/src/melliscribe/models/trace.py` with `recording_id`, `stage`, `provider`, `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cost_usd`, `latency_ms`, `outcome` and `fallback_taken`
- [ ] T037 Implement the trace writer in `backend/src/melliscribe/pipeline/tracing/writer.py` with a per-model rate table that carries the date it was last checked, so a stale rate is visible in the data rather than silently wrong (ADR-0006)
- [ ] T038 Write a test in `backend/tests/unit/test_tracing.py` asserting that an error and a timeout each write a trace row with the right outcome — errors are recorded, never swallowed (Principle VI)

### Minimal eval harness (ADR-0005 — kept deliberately thin here)

- [ ] T039 Implement the eval runner in `backend/evals/harness/runner.py` with separate entry points per pipeline stage and separately recorded baselines (ADR-0005)
- [ ] T040 Implement `melliscribe eval run` and `melliscribe eval compare` in `backend/src/melliscribe/cli/eval.py` so CI and a local run use the identical entry point
- [ ] T041 Define the dataset manifest format in `backend/evals/datasets/README.md`, requiring each entry to carry a private-storage reference plus either a consent reference or a purpose-made marker (FR-027f)
- [ ] T042 Add `melliscribe eval run --dataset datasets/smoke.jsonl` to `.github/workflows/ci.yml` as a blocking job (Principle II)

**Checkpoint**: ADR-0002 is Accepted. Vocabularies exist and are label-complete. The Pydantic models generate both the OpenAPI schema and the frontend types, and CI fails on drift. A six-recording eval gate runs green.

---

## Phase 3: User Story 1 — Dictate an inspection at the hive (Priority: P1) 🎯 MVP

**Goal**: A beekeeper speaks an inspection offline, gets an explicit confirmation that their words are safe, and once online receives a structured record with unknowns flagged rather than guessed — reviewable and correctable in both languages.

**Independent test**: Airplane mode, dictate a full inspection out loud, confirm the app says the recording is stored; restore connectivity and confirm the record's filled fields match what was said and unmentioned fields are marked unknown.

### Tests for User Story 1

- [ ] T043 [P] [US1] Write a contract test for `POST /recordings` in `backend/tests/contract/test_recordings_post.py` asserting `201` on first upload and `200` on a repeat of the same client-generated id, with no duplicate record (FR-020)
- [ ] T044 [P] [US1] Write a contract test for `POST /hives` in `backend/tests/contract/test_hives_post.py` asserting `201` on creation and `409` on a duplicate identifier (FR-015a, FR-015d)
- [ ] T045 [P] [US1] Write a contract test for `PATCH /records/{id}` in `backend/tests/contract/test_records_patch.py` asserting any field set there becomes `CONFIRMED` and survives later extraction (FR-010)
- [ ] T046 [P] [US1] Write an integration test in `backend/tests/integration/test_offline_capture.py` asserting a recording is durably persisted before success is reported and is not discarded until the server acknowledges it (FR-002, FR-003)
- [ ] T047 [P] [US1] Write an extraction test in `backend/tests/integration/test_extraction_unknowns.py` asserting a transcript that never mentions stores yields `UNKNOWN` with a null value, and never a default or carried-over value (FR-007, SC-004)
- [ ] T048 [P] [US1] Write an extraction test in `backend/tests/integration/test_extraction_caching.py` asserting `usage.cache_read_input_tokens` is non-zero on the second call — a zero means the prompt prefix is being invalidated and every call pays full price (ADR-0003)
- [ ] T049 [P] [US1] Write a Playwright test in `frontend/tests/capture-offline.spec.ts` driving the capture flow with the network disabled, asserting the safe-storage confirmation appears

### Capture — frontend (FR-001 to FR-004)

- [ ] T050 [US1] Implement the IndexedDB wrapper in `frontend/src/offline/db.ts` with separate object stores for audio blobs and the pending-operations queue (ADR-0004)
- [ ] T051 [US1] Implement audio capture in `frontend/src/capture/recorder.ts` using `MediaRecorder`, detecting and storing the produced format rather than assuming it (D9)
- [ ] T052 [US1] Generate the recording UUID on the device at capture time in `frontend/src/capture/recorder.ts` — it is the upload idempotency key and the batch `custom_id` (FR-020, ADR-0004)
- [ ] T053 [US1] Write the recording to IndexedDB and only then show the confirmation, in `frontend/src/capture/CaptureScreen.tsx` (FR-002)
- [ ] T054 [US1] Implement gloved-hands capture controls in `frontend/src/capture/CaptureControls.tsx` — large, widely spaced, tolerant of imprecise taps, with no hover-dependent or long-press-only action on the path (FR-004)
- [ ] T055 [US1] Display the active language on the capture screen without requiring any action, so a wrong setting is noticeable before a dictation rather than after (FR-026d, US1 scenario 12)
- [ ] T056 [US1] Implement the upload queue with backoff in `frontend/src/offline/queue.ts`, treating Background Sync as an optimisation and the foreground retry as the guarantee, and never dropping a local copy before a `201` or `200` (FR-003, ADR-0004)
- [ ] T057 [US1] Warn the beekeeper before local storage is exhausted by unprocessed recordings, in `frontend/src/offline/quota.ts` (FR-021)

### Capture — backend

- [ ] T058 [US1] Implement `POST /recordings` in `backend/src/melliscribe/api/recordings.py` as a thin router, idempotent on the client-generated id, returning `415` for an unsupported format without discarding the file (FR-005, FR-020)
- [ ] T059 [US1] Implement durable audio storage in `backend/src/melliscribe/db/audio_store.py`, acknowledging only after the write is durable (FR-003)

### Transcription (blocked by T011)

- [ ] T060 [US1] Implement the chosen ADR-0002 backend in `backend/src/melliscribe/pipeline/transcription/` behind the `TranscriptionBackend` protocol, returning segment-level timestamps
- [ ] T061 [US1] Write the trace row for every transcription call from `backend/src/melliscribe/pipeline/transcription/` via the writer from T037 (Principle VI)
- [ ] T062 [US1] Implement `melliscribe transcribe` in `backend/src/melliscribe/cli/transcribe.py` with a `--json` mode, exercising the backend with no database and no API (Code Standards)

### Extraction (ADR-0003)

- [ ] T063 [US1] Generate the extraction JSON Schema from the Pydantic model in `backend/src/melliscribe/pipeline/extraction/schema.py` — generated, never hand-written, or the single-source-of-truth chain breaks at its most important link
- [ ] T064 [US1] Create the versioned extraction prompt in `backend/src/melliscribe/pipeline/extraction/prompts/v1.md` ordered stable-prefix-first: system instructions, controlled vocabularies, glossary, few-shot examples in both languages, then the transcript last (D5, ADR-0003)
- [ ] T065 [US1] Implement the Claude extractor in `backend/src/melliscribe/pipeline/extraction/claude.py` using `claude-opus-5` with `output_config.format`, adaptive thinking, and a `cache_control` breakpoint after the few-shot block
- [ ] T066 [US1] Define the uncertainty threshold as an explicit versioned documented value in `backend/src/melliscribe/pipeline/extraction/thresholds.py`, recorded in each record's provenance (FR-008, FR-008a)
- [ ] T067 [US1] Implement field-status assignment in `backend/src/melliscribe/domain/inspection/status.py`: unmentioned becomes `UNKNOWN` with a null value, below-threshold becomes `UNCERTAIN`, and an unmappable observation becomes `UNCERTAIN` retaining the verbatim phrase rather than being forced to the nearest value (FR-007, FR-008, FR-006d)
- [ ] T068 [US1] Implement proposal handling in `backend/src/melliscribe/domain/inspection/status.py` so an `UNCERTAIN` field may carry a proposed value that is never treated as set for history, export or trend until confirmed (FR-006e)
- [ ] T069 [US1] Implement spoken self-correction handling so the later statement supersedes the earlier one, and an unclear correction flags the field rather than resolving to either (FR-006f, US1 scenario — prompt rule 7)
- [ ] T070 [US1] Write the trace row for every extraction call, including `cache_read_tokens`, from `backend/src/melliscribe/pipeline/extraction/claude.py` (Principle VI, ADR-0006)
- [ ] T071 [US1] Implement `melliscribe extract` and `melliscribe pipeline` in `backend/src/melliscribe/cli/extract.py` with `--json`, `--prompt-version` and `--no-cache` — this is the replay command for a field failure (Code Standards)

### Hive identity (FR-015)

- [ ] T072 [P] [US1] Implement `GET /hives` and `POST /hives` in `backend/src/melliscribe/api/hives.py`, refusing a duplicate identifier with `409` rather than disambiguating silently (FR-015a, FR-015d)
- [ ] T073 [US1] Implement hive matching from a spoken identifier in `backend/src/melliscribe/domain/inspection/hive_match.py`, flagging rather than guessing when no match is found and never creating a hive on its own (FR-015, FR-015c)
- [ ] T074 [US1] Implement `POST /records/{id}/resolve-hive` in `backend/src/melliscribe/api/records.py` accepting either an existing `hive_id` or an identifier to create (FR-015b, US1 scenario 10)
- [ ] T075 [US1] Implement multi-hive detection in `backend/src/melliscribe/domain/inspection/hive_match.py` producing a single record with the hive field flagged and an explanation, never splitting the dictation or attributing it to one of the hives named (FR-015e, US1 scenario 16)

### Dates and empty dictations

- [ ] T076 [P] [US1] Implement inspection-date resolution in `backend/src/melliscribe/domain/inspection/dates.py` defaulting to capture time and preferring a spoken date, flagging when the two differ by more than a day with both dates kept visible (FR-016, FR-016a, US1 scenario 17)
- [ ] T077 [P] [US1] Implement empty-dictation handling so an intelligible transcript with no inspection content produces no record, tells the beekeeper nothing was recognised, and retains the recording (FR-016b, US1 scenario 18)

### Review and correction (FR-022, FR-024)

- [ ] T078 [US1] Implement `GET /records` and `GET /records/{id}` in `backend/src/melliscribe/api/records.py`, each observation field carrying its status, verbatim phrase and segment reference so review needs no second call
- [ ] T079 [US1] Implement `PATCH /records/{id}` so any field set becomes `CONFIRMED` and is permanently immune to later extraction (FR-010, FR-022)
- [ ] T080 [US1] Implement `POST /records/{id}/confirm` in `backend/src/melliscribe/api/records.py`, with an unconfirmed record remaining a valid saved state (FR-024)
- [ ] T081 [US1] Build the review screen in `frontend/src/review/RecordReview.tsx` showing each field's status and the verbatim phrase it came from, visibly distinguishing system-derived from beekeeper-confirmed values (FR-006b, FR-009)
- [ ] T082 [US1] Ensure the raw confidence score is never rendered as a number — status is the beekeeper-facing signal (FR-009)
- [ ] T083 [US1] Implement gloved-hands correction controls in `frontend/src/review/FieldEditor.tsx` (FR-004, SC-006)

### Language integrity (Principle VIII)

- [ ] T084 [P] [US1] Implement `GET /settings` and `PATCH /settings` in `backend/src/melliscribe/api/settings.py` for `language` and `audio_retention_days`, never inferring language from request origin (FR-026)
- [ ] T085 [US1] Persist the language setting for offline availability in `frontend/src/offline/settings.ts` and apply it to every recording with no choice presented at capture time (FR-026, FR-026a)
- [ ] T086 [US1] Implement `POST /recordings/{id}/reprocess` in `backend/src/melliscribe/api/recordings.py` accepting a corrected language and merging rather than replacing, so already-`CONFIRMED` fields are preserved (FR-026b, FR-026c)
- [ ] T087 [US1] Surface a detected-versus-account language disagreement on the record and offer re-processing, without ever switching languages automatically (FR-026e, US1 scenario 13)
- [ ] T088 [US1] Implement mixed-language handling so extraction runs against the account language, flags fields whose source phrase was in the other language, and is not abandoned (FR-026f, US1 scenario 14)
- [ ] T089 [US1] Localise every user-facing string through the i18n catalogues, including API error messages, validation messages and vocabulary labels (FR-025)
- [ ] T090 [US1] Format dates, numbers and quantities for the active language in the review flow (FR-025a)

### Failure handling

- [ ] T091 [US1] Record which stage produced a failure in `backend/src/melliscribe/pipeline/` so a wrong record is attributable to transcription or extraction rather than to "the system" (FR-019b, US2 scenario 7)
- [ ] T092 [US1] Implement re-processing failure handling so the previous record stays intact and the beekeeper is told it did not take (FR-019c, US1 scenario 15)

### Closing US1 — the full eval set

- [ ] T093 [US1] Grow `backend/evals/datasets/extraction.jsonl` and `transcription.jsonl` to at least 50 dictations per language, of which at least 20 are paired — the same inspection dictated once in each language (spec Assumptions, SC-005, SC-011)
- [ ] T094 [US1] Implement the SC-004 eval check in `backend/evals/harness/` asserting zero fields populated from unmentioned content, failing the build on any occurrence
- [ ] T095 [US1] Implement the SC-005 and SC-011 parity checks — French field accuracy within 5 points of English, counting a field accurate only when coded value and status both match, and identical coded values on paired dictations
- [ ] T096 [US1] Implement the SC-010 glossary-recall check at 95% per language, and the transcription word error rate baseline per language (FR-014, SC-010)
- [ ] T097 [US1] Calibrate the uncertainty threshold from T066 against the eval set so SC-003 holds, and record the chosen value in `docs/adr/0003-claude-structured-outputs.md` (FR-008a, SC-003)
- [ ] T098 [US1] Switch the CI eval job from `smoke.jsonl` to the full datasets in `.github/workflows/ci.yml`

**Checkpoint**: US1 is independently deliverable. A beekeeper can dictate offline, get a record, review and correct it, in French or English, with the eval gate live.

---

## Phase 4: User Story 2 — Process a recording later, from a file (Priority: P2)

**Goal**: Audio the app did not capture live — a voice memo, a handheld recorder, or a long offline backlog — yields the same record without re-dictating.

**Independent test**: Submit a pre-existing audio file with no live capture involved and confirm it produces a record equivalent to what the live flow would produce from the same speech.

### Tests for User Story 2

- [ ] T099 [P] [US2] Write an integration test in `backend/tests/integration/test_file_import.py` asserting a submitted audio file yields the same fields, flagging and review flow as a live dictation (US2 scenario 1)
- [ ] T100 [P] [US2] Write an integration test in `backend/tests/integration/test_batch_extraction.py` asserting several queued recordings each produce their own record with none skipped or merged, keyed by `custom_id` and tolerant of arbitrary result order (US2 scenario 2, D4)
- [ ] T101 [P] [US2] Write an integration test in `backend/tests/integration/test_retry.py` asserting a transcript that succeeded is reused when only extraction failed, and the audio is not transcribed a second time (FR-019a, US2 scenario 6)

### Implementation for User Story 2

- [ ] T102 [US2] Implement file submission in `frontend/src/capture/FileImport.tsx` accepting formats the app did not produce, with a clear message and retained file on an unsupported format (FR-005)
- [ ] T103 [US2] Implement batch extraction in `backend/src/melliscribe/pipeline/extraction/batch.py` through the Message Batches API at 50% cost, using the recording UUID as `custom_id` and keying results by it rather than by position (D4, ADR-0003)
- [ ] T104 [US2] Implement the processing queue worker in `backend/src/melliscribe/pipeline/queue.py` driving recordings through the state machine from data-model.md
- [ ] T105 [US2] Implement `GET /recordings` filtering by state so the beekeeper can see what is queued and what has failed (FR-018)
- [ ] T106 [US2] Build the pending-work view in `frontend/src/review/PendingList.tsx` showing queued and failed recordings with their failure reason (FR-018, US2 scenario 3)
- [ ] T107 [US2] Implement `POST /recordings/{id}/retry` preserving the recording across failures and reusing an existing transcript (FR-019, FR-019a)
- [ ] T108 [US2] Ensure SC-007 holds — a recording captured offline is processed and its record available within 5 minutes of connectivity returning

**Checkpoint**: US1 and US2 both work independently.

---

## Phase 5: User Story 3 — Hear what was actually said (Priority: P3)

**Goal**: A beekeeper can play back the audio passage a field came from, to tell "the system misunderstood me" from "I misspoke".

**Independent test**: Open any populated field on a record from either flow and confirm the audio plays from the passage that phrase was taken from.

### Tests for User Story 3

- [ ] T109 [P] [US3] Write a contract test in `backend/tests/contract/test_audio_range.py` asserting `GET /recordings/{id}/audio` supports range requests and returns `410 Gone` once the audio is deleted or aged out
- [ ] T110 [P] [US3] Write a test in `backend/tests/integration/test_segment_refs.py` asserting each populated field's segment reference resolves to the transcript segment its phrase came from (FR-023)

### Implementation for User Story 3

- [ ] T111 [US3] Implement `GET /recordings/{id}/audio` in `backend/src/melliscribe/api/recordings.py` with range support and `410` when unavailable
- [ ] T112 [US3] Implement per-field playback in `frontend/src/review/FieldPlayback.tsx` starting at the segment the phrase came from rather than at the beginning of the recording (FR-023, US3 scenario 1)
- [ ] T113 [US3] Render an honest unavailable state where playback would otherwise be offered, once the audio is gone (FR-027d, US4 scenario 5)

**Checkpoint**: All three interpretation stories work.

---

## Phase 6: User Story 4 — Decide how long my voice is kept (Priority: P4)

**Goal**: The beekeeper can see and change how long recordings are kept, delete any recording immediately, and keep the record when the audio goes.

**Independent test**: Produce a record, delete its recording, and confirm the record and transcript survive intact while playback is honestly reported as unavailable; then change the retention period and confirm it takes effect.

### Tests for User Story 4

- [ ] T114 [P] [US4] Write a test in `backend/tests/integration/test_retention.py` asserting a deleted recording leaves the record and transcript intact with every field still showing its verbatim phrase (FR-027c, US4 scenario 4)
- [ ] T115 [P] [US4] Write a test in `backend/tests/integration/test_retention_expiry.py` asserting the beekeeper is warned before expiry removes anything, and warned louder when the record still has unconfirmed or flagged fields (FR-027e, US4 scenarios 6 and 7)

### Implementation for User Story 4

- [ ] T116 [US4] Implement the retention period in `backend/src/melliscribe/domain/retention/policy.py`, defaulting to 365 days and changeable per account (FR-027a)
- [ ] T117 [US4] Implement `DELETE /recordings/{id}` in `backend/src/melliscribe/api/recordings.py` removing the audio immediately regardless of the retention setting and leaving the record and transcript untouched (FR-027b, FR-027c)
- [ ] T118 [US4] Implement expiry in `backend/src/melliscribe/domain/retention/expiry.py` and the `melliscribe retention due` and `melliscribe retention apply --dry-run` commands in `backend/src/melliscribe/cli/retention.py`
- [ ] T119 [US4] Implement expiry warnings, including the louder warning when a record still has unconfirmed or flagged fields whose evidence is about to go (FR-027e)
- [ ] T120 [US4] Build the retention settings screen in `frontend/src/review/RetentionSettings.tsx` showing the current period and offering immediate deletion (FR-027a, FR-027b, US4 scenarios 1 to 3)
- [ ] T121 [US4] Implement per-recording consent recording with its date, and require every eval dataset entry to carry a consent reference or a purpose-made marker (FR-027f)

**Checkpoint**: All four stories complete.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T122 [P] Write the ADR for authentication if this feature's single-beekeeper assumption is relaxed, in `docs/adr/`
- [ ] T123 [P] Add the aggregate trace queries from quickstart.md scenario 9 to `backend/src/melliscribe/cli/trace.py` so cost per inspection and latency percentiles are answerable without a one-off script (Principle VI)
- [ ] T124 [P] Verify SC-001 — a routine inspection dictated and saved in under 90 seconds of the beekeeper's attention
- [ ] T125 [P] Verify SC-006 outdoors with gloves — 90% of beekeepers through their first dictated inspection unassisted
- [ ] T126 [P] Add `docs/` user-facing documentation naming every external service that receives user content, in user-facing terms (Principle III, FR-027)
- [ ] T127 [P] Add a CHANGELOG entry describing the user-visible feature, with no internal names, tests, CI or tooling mentioned (Constitution, Releases)
- [ ] T128 Walk every quickstart.md scenario end to end and record the results
- [ ] T129 Measure whether extraction cost per record is dominated by the cached prefix, and record the finding in `docs/adr/0003-claude-structured-outputs.md` — this closes CHK043, the one checklist item left open on purpose

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)** — no dependencies
- **Phase 2 (Foundational)** — depends on Phase 1. **Blocks every user story.**
- **Phase 3 (US1)** — depends on Phase 2. T060 onward additionally blocked by **T011** (ADR-0002 Accepted)
- **Phase 4 (US2)** — depends on Phase 2; reuses the US1 pipeline but is independently testable
- **Phase 5 (US3)** — depends on Phase 2 and on segment timestamps existing (T034, T060)
- **Phase 6 (US4)** — depends on Phase 2 only; the least coupled story
- **Phase 7 (Polish)** — depends on the stories it touches

### Critical path

```
T001-T008 ──> T009-T011 (ADR-0002 spike) ──> T060 (transcription) ──┐
         └──> T012-T016 (vocabularies) ──> T063-T069 (extraction) ──┴──> US1 closes
```

The ADR-0002 spike and the vocabulary work are independent of each other and
can run in parallel. Both block extraction.

### User Story Dependencies

- **US1** is self-contained once Phase 2 is done
- **US2** shares the pipeline with US1 but its file-import and batch paths are separately testable
- **US3** needs segment timestamps, which T034 requires of any backend
- **US4** touches almost nothing US1 touches and could be built at any point after Phase 2

### Parallel Opportunities

**Phase 2**: T009–T011 (ADR spike) ∥ T012–T016 (vocabularies) ∥ T017–T027 (models, most marked [P]) ∥ T028–T030 (database)

**Phase 3**: all seven test tasks T043–T049 in parallel; then frontend capture (T050–T057) ∥ backend capture (T058–T059) ∥ hive identity (T072–T075) ∥ dates (T076–T077)

**Phase 7**: T122–T127 all parallel

---

## Implementation Strategy

### MVP scope

**User Story 1 alone**, which means Phases 1, 2 and 3 — tasks T001 through T098.

That is the whole product promise: dictate offline, get a trustworthy record,
review it in either language. US2, US3 and US4 each add real value and none is
required for a beekeeper to use this in an apiary.

### Order to actually work in

1. **Phases 1 and 2**, with the ADR-0002 spike (T009–T011) started first because
   it is the longest lead time and it blocks transcription.
2. **A thin vertical slice of Phase 3**: T050–T053 (capture to IndexedDB),
   T058–T059 (upload), T060 (transcription), T063–T065 (extraction), T078 and
   T081 (see the record). At that point something works end to end and the
   project stops being invisible.
3. **Widen Phase 3** — flagging rules, hive identity, language integrity,
   review controls.
4. **Close US1** with the full eval set (T093–T098).
5. **US2, then US3, then US4**, each shippable on its own.

### The risk to manage

ADR-0005 states it plainly: the eval gate means the first stretch produces
nothing visible, and for a solo maintainer with a few hours a week that is the
most likely abandonment point. Step 2 above exists to counter it — reach a
working end-to-end path early, on a six-recording eval set, and grow the
dataset afterwards. **Do not build T093–T098 before T050–T081.**
