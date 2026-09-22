# Melliscribe

**Speak at the hive, get an inspection record.**

A beekeeper works with gloves on, a frame in one hand and often no signal.
Melliscribe lets them dictate an inspection — in French or English — and turns
it into a structured record: hive, date, queen, brood, stores, temperament,
frame counts, treatments and actions to do.

Two promises shape everything else:

- **Nothing said is lost.** A recording is stored safely on the phone before
  the app says so, and stays there until the server confirms it has it. Capture
  works with no network at all.
- **Nothing is guessed.** A field the beekeeper didn't mention is marked "not
  mentioned"; anything heard unclearly is marked "needs checking". Every value
  shows the words it came from, and the beekeeper's corrections always win.

## Status

Early development. The first feature, [voice inspection capture](specs/001-voice-inspection-capture/spec.md),
is implemented end to end:

| Part | State |
|---|---|
| Offline capture, upload queue, review and correction (PWA) | Working |
| Extraction with Claude | Working — passes the 32-case bilingual smoke eval |
| Speech recognition | **Provisional**: self-hosted Whisper, while [ADR-0002](docs/adr/0002-asr-provider.md) compares providers on real recordings |
| Full evaluation dataset (50 dictations per language) | Not yet recorded |
| Field trials with gloves | Not yet run |

## How it works

```
phone (PWA, offline-first)            server
┌─────────────────────────┐           ┌──────────────────────────────────────────┐
│ record → IndexedDB      │  upload   │ audio ──► transcription ──► extraction   │
│ upload queue, retries   │ ────────► │           (Whisper,         (Claude,     │
│ review & correct        │ ◄──────── │            ADR-0002)         ADR-0003)   │
└─────────────────────────┘  records  │                     ▼                    │
                                      │     domain rules: statuses, counts,      │
                                      │     hive matching, dates → record        │
                                      └──────────────────────────────────────────┘
```

- **Two stages, separately evaluated** ([ADR-0001](docs/adr/0001-two-stage-pipeline.md)).
  A wrong record can be traced to a mishearing or a misreading.
- **One definition of the data.** Pydantic models generate the schema Claude
  must follow, the OpenAPI schema and the frontend's TypeScript types. CI fails
  if they drift.
- **Rules in code, not in the prompt.** Claude reports what it heard. What the
  beekeeper is told to trust (the uncertainty threshold, controlled vocabularies,
  frame-count limits, contradictions) is decided by tested domain code.
- **Every model call is traced** with cost and latency, in a database table.

## Getting started

Requirements: Python 3.13 with [uv](https://docs.astral.sh/uv/), Node 20+, and
ffmpeg if you use local speech recognition. PostgreSQL is the system of record;
without `MELLISCRIBE_DATABASE_URL`, development falls back to SQLite.

```bash
# Backend
uv sync --project backend --extra asr-local        # drop the extra to skip Whisper
(cd backend && uv run alembic upgrade head)

# Frontend
npm --prefix frontend ci
```

Run it:

```bash
export ANTHROPIC_API_KEY=...                        # extraction; keep it out of the repo
export MELLISCRIBE_ASR_PROVIDER=faster-whisper      # provisional local transcription
uv run --project backend uvicorn --factory melliscribe.api.app:create_app --port 8000
uv run --project backend melliscribe worker         # processes queued recordings
npm --prefix frontend run dev                       # http://localhost:5173, proxies /api
```

To look at the review screens without dictating, seed a record from a typed
transcript (one line per sentence):

```bash
(cd backend && uv run melliscribe dev seed notes.txt --language fr --hive 3)
```

### Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Extraction and the extraction evals |
| `MELLISCRIBE_DATABASE_URL` | SQLite in `var/` | e.g. `postgresql+psycopg://…` |
| `MELLISCRIBE_DATA_DIR` | `var` | Local database and audio in development |
| `MELLISCRIBE_AUDIO_DIR` | `$DATA_DIR/audio` | Where recordings are stored |
| `MELLISCRIBE_ASR_PROVIDER` | `unconfigured` | `faster-whisper` for local transcription |
| `MELLISCRIBE_ASR_MODEL` | `small` | Whisper model size |
| `MELLISCRIBE_PROCESS_ON_UPLOAD` | `true` | `false` leaves processing to `melliscribe worker` (recommended with local Whisper) |
| `MELLISCRIBE_EVAL_STORAGE` | `~/.melliscribe/evals` | Private evaluation audio and transcripts |
| `VITE_API_BASE` | `/api` | API base URL for the PWA |

## Command line

Every backend capability has a CLI, which is also how a reported field failure
is replayed locally:

```
melliscribe transcribe <audio> --language fr|en     transcription only
melliscribe extract <transcript|-> --language …     extraction only
melliscribe pipeline <audio> --language …           both stages, as the API runs them
melliscribe eval run --dataset datasets/smoke.jsonl the evaluation gate
melliscribe vocabulary check                         labels, glossary, released values
melliscribe retention due | apply --dry-run          audio expiry
melliscribe trace summary                            cost and latency per stage
melliscribe worker | openapi | dev seed
```

All of them take `--json`.

## Tests and quality gates

```bash
cd backend
uv run ruff check . && uv run ruff format --check . && uv run ty check
uv run pytest                       # SQLite; set MELLISCRIBE_DATABASE_URL for PostgreSQL
uv run pytest -m live               # calls the real API; needs a key
uv run melliscribe vocabulary check

cd ../frontend
npm run typecheck && npm test && npm run test:e2e
```

CI also regenerates the OpenAPI schema and TypeScript types and fails on any
difference, and runs the extraction eval, which needs an `ANTHROPIC_API_KEY`
repository secret. A smoke eval run costs about $0.50.

## Privacy

This repository is public; beekeepers' data is not. No recording or transcript
of a real inspection is ever committed: evaluation datasets point at private
storage, and the smoke set is synthetic. The services that receive a beekeeper's
content are listed, in French and English, in
[docs/external-services.md](docs/external-services.md).

## Project documents

- [Constitution](.specify/memory/constitution.md): the principles every change is held to
- [Architecture decisions](docs/adr/README.md)
- [Feature 001 specification, plan and tasks](specs/001-voice-inspection-capture/)
- [Changelog](CHANGELOG.md)

Features are planned with [Spec Kit](https://github.com/github/spec-kit)
(`specs/`), commits follow [Conventional Commits](https://www.conventionalcommits.org/),
and `pre-commit install` sets up the hooks, including license headers.

## License

[GNU Affero General Public License v3.0 or later](LICENSE). Copyright (C) 2026 Jean-Christophe Giret.

If you run a modified Melliscribe as a service, the AGPL requires you to offer
its source to the users of that service.
