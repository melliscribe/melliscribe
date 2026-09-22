# AGENTS.md

Instructions for coding agents working in this repository. The
[constitution](.specify/memory/constitution.md) governs; if anything here
disagrees with it, the constitution wins and this file is wrong.

## What this is

Melliscribe turns a beekeeper's dictated hive inspection (French or English)
into a structured record. FastAPI + Pydantic v2 backend in `backend/`, React +
TypeScript PWA in `frontend/`. Planning lives in `specs/` (Spec Kit), decisions
in `docs/adr/`.

## Commands

Run from the directory shown.

```bash
# backend/
uv sync --extra asr-local           # dependencies (+ optional local Whisper)
uv run pytest                       # full suite, SQLite, no network
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run melliscribe vocabulary check # both-language labels, glossary, vocabulary lock
uv run alembic revision --autogenerate -m "…" --rev-id 000N   # new migration

# frontend/
npm run typecheck && npm test       # tsc strict + vitest
npm run test:e2e                    # Playwright, offline capture

# after any change to a Pydantic model used by the API (run from the repo root)
uv run --project backend melliscribe openapi --output backend/openapi.json
npm --prefix frontend run generate:api
```

**Commands that cost money**: `uv run pytest -m live` and
`uv run melliscribe eval run …` call the Anthropic API (a full smoke eval is
about $0.50). Run them only when asked, or when a change requires them (see
below). The key is read from the environment, from a file outside the
repository; never read it back, print it or put it in a command line.

## Rules that are enforced (CI or review)

- **Test first.** Write the failing test, see it fail, then implement. Bugs
  start with a regression test.
- **Pydantic is the source of truth.** Never hand-write a TypeScript type that
  mirrors a backend model; use `frontend/src/api/generated/`. Regenerate after
  model changes, and commit the regenerated files.
- **Database changes are Alembic migrations**, forward-tested by
  `tests/integration/test_migrations.py`. In migrations, use plain SQLAlchemy
  types (`sa.DateTime(timezone=True)`), never app classes.
- **Bilingual by construction.** Every user-facing string, API error messages
  included, comes from a catalogue: `frontend/src/i18n/{fr,en}.json` and
  `backend/src/melliscribe/i18n/{fr,en}.json`. Add every key in both languages.
  Maintainer CLI output stays English.
- **Controlled vocabularies** (`models/vocabulary.py`) are language-neutral ids
  with a definition and both labels. Once a value is released it is superseded,
  never removed or redefined; `vocabulary.lock.json` enforces this.
- **LLM changes need an eval.** Any change to a prompt
  (`pipeline/extraction/prompts/vN.md`, new version file, never edit in place),
  the extraction schema, a vocabulary, the glossary or the uncertainty
  threshold needs `melliscribe eval run --dataset datasets/smoke.jsonl`, with
  the result in the PR. Bump `EXTRACTION_SCHEMA_VERSION` / `VOCABULARY_VERSION`
  / `GLOSSARY_VERSION` / `THRESHOLD_VERSION` with the change.
- **Privacy.** Never commit audio, real transcripts, eval data from users,
  secrets or `.env` files. Synthetic, purpose-made cases only in
  `backend/evals/datasets/`.
- **ADRs are append-only.** A reversal is a new ADR; a finding is an addendum.
- **Python style**: `from __future__ import annotations` first; one import per
  line; type hints everywhere; Google docstrings in mkdocs syntax, with `Args:`
  and `Returns:` whenever applicable, private functions included; function names
  start with a verb; enum members CAPITAL_CASED; the license header from
  `LICENSE_HEADER.txt` on every source file.
- **TypeScript**: `strict`; `any` needs a written justification.
- **Commits**: Conventional Commits. Commit or push only when asked.

## How the pipeline is built (read before touching extraction)

- `pipeline/transcription/` — `TranscriptionBackend` protocol. ADR-0002 is
  still open; `faster_whisper.py` is a provisional candidate.
- `pipeline/extraction/` — Claude with structured outputs. The JSON Schema is
  **generated** from `ExtractionOutput`; never hand-write it.
  - **Grammar limit**: structured outputs compile each distinct object type,
    and a typed object per field exceeded the limit. Observations are therefore
    one flat list (`Observation`), read back per field by `observations.py`.
    A new *kind* of field adds an object type: check it compiles against the
    API before merging.
- `domain/inspection/` — everything the beekeeper is told to trust: statuses
  and the threshold (`status.py`), counts and contradictions (`counts.py`),
  hive matching, dates, record assembly, corrections. The model reports; this
  code decides. It must stay pure: no database, no API, no provider.
- `pipeline/process.py` and `pipeline/queue.py` — state transitions and
  failure attribution. Recordings are never lost; a successful transcript is
  reused; re-processing is all or nothing and keeps confirmed fields.
- `api/` routers are thin adapters. Logic belongs in `domain/` or `pipeline/`.

Invariants worth knowing before changing models or assembly:

- An `UNKNOWN` field never carries a value or proposal (validator in
  `models/inspection.py`). SC-004 has zero tolerance.
- An `UNCERTAIN` field carries a proposal, never a value.
- A `CONFIRMED` field is never overwritten by extraction.

## Spec Kit workflow

Feature work goes through `/speckit-*` commands in `.claude/skills/`: specify,
clarify, plan, tasks, implement, converge, analyze. The spec is authoritative:
if code needs a behaviour the spec lacks, amend the spec first. Mark finished
tasks `[X]` in `tasks.md`; record divergences in `plan.md` or `data-model.md`.
Checklists in `specs/*/checklists/` other than `requirements.md` belong to the
reviewer; don't tick them.
