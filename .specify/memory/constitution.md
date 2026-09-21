# Melliscribe Constitution

Melliscribe is an AI-first beekeeping journal. A beekeeper speaks at the hive —
often with no network, gloves on, in the middle of an inspection — and the system
turns that speech into a structured record of hive state, actions performed, and
actions still to do. Every principle below exists to protect that moment: the
record must survive the field, and the beekeeper must stay the authority over
what their own logbook says.

## Core Principles

### I. Library-First, CLI-Exposed

Every non-trivial capability MUST be implemented as a self-contained, independently
testable library before any HTTP route, React component, or mobile shell depends on
it. Domain logic (hive state transitions, inspection parsing, audio handling, sync
reconciliation) MUST NOT live in FastAPI route handlers or React components; those
layers are adapters and stay thin.

Each backend library MUST expose its core operations through a CLI with a text/JSON
protocol: arguments and stdin in, stdout out, errors and diagnostics to stderr, with
both a human-readable and a `--json` output mode. Organizational-only libraries —
packages that exist to group code rather than to own a capability — are forbidden.

**Rationale**: A CLI is the cheapest possible integration test, the fastest debugging
surface when a field recording produces a wrong record, and the only way to replay a
production failure locally without standing up the full stack.

### II. Test-First (NON-NEGOTIABLE)

Tests are written before the implementation, reviewed and approved as a specification
of intended behavior, observed to fail, and only then made to pass. Red-Green-Refactor
is enforced, not encouraged.

The following MUST have tests before the code exists:
- Every library contract and every change to one.
- Every API endpoint contract (request schema, response schema, status codes, errors).
- Every offline-to-online sync path, including conflict cases.
- Every database migration, exercised forward against a seeded database.

Bug fixes MUST begin with a failing regression test that reproduces the bug. A pull
request that adds behavior with no test that would have failed beforehand MUST NOT
merge.

**Rationale**: The failure mode of a journal is silent data loss or a quietly wrong
record, neither of which a user notices until the season is over and the evidence is
gone. Tests written afterwards are written to pass, and encode the bug.

### III. Typed, Linted, Conventional

All Python sources MUST begin with `from __future__ import annotations`, carry type
hints on every public signature, and pass `ruff` lint and format plus the project's
type checker with zero suppressions that lack an inline justification. Imports are
single-line (`force-single-line = true`). Docstrings follow the Google convention in
mkdocs/markdown syntax — `[ClassName][module.ClassName]`, never Sphinx RST — and MUST
include an `Args:` section whenever the callable takes parameters beyond `self`/`cls`
and a `Returns:` section whenever it returns a non-`None` value, private and
`@staticmethod` callables included.

Callables MUST be named starting with a verb (`transcribe_recording`,
`compute_colony_strength`); noun-only names are reserved for attributes and
properties. Enum member keys are CAPITAL_CASED. License headers are required on all
source files. TypeScript MUST run under `strict` mode; `any` requires a written
justification at the use site.

Schemas are Pydantic v2 models on the backend and generated types on the frontend.
Hand-maintained duplicate type definitions across the API boundary are forbidden —
the client's types MUST be derived from the server's OpenAPI schema.

**Rationale**: This is a solo side project worked on in bursts across seasons. The
type checker and linter are the reviewers who are always awake, and a generated client
is the only way a schema change cannot silently desynchronize the app from the server.

### IV. Offline-First Data Integrity

Offline is the normal operating condition, not a degraded one. An apiary has no
signal, and the app MUST behave as though it never will.

- Capture MUST succeed with no network: audio, structured edits, and notes are
  written to durable local storage (IndexedDB on the PWA, native storage under
  Capacitor) before any UI confirms success to the user.
- Locally captured data MUST NOT be discarded until the server has acknowledged
  durable receipt. Upload failures retry; they never drop.
- Every record carries a client-generated stable identifier and a logical timestamp,
  so that sync is idempotent and a retried upload cannot duplicate an inspection.
- Conflict resolution MUST be explicit and documented per entity type. Silent
  last-write-wins over a beekeeper's field notes is forbidden; unresolvable conflicts
  are surfaced to the user with both versions intact.
- No user-visible destructive operation may be applied server-side as a consequence
  of sync alone.

**Rationale**: A lost inspection cannot be reconstructed — the hive has already been
closed and the beekeeper has moved on. Data loss here is permanent in a way that a
missing API response is not.

### V. AI Output Is A Draft, Never The Record

Transcription and extraction produce proposals. The beekeeper's confirmation produces
the record.

- Raw audio and raw transcript MUST be retained and remain retrievable alongside any
  structured record derived from them, so a wrong extraction is always traceable and
  correctable against the source.
- Every AI-derived field MUST be visibly attributable as AI-derived and MUST be
  editable by the user. A user edit permanently wins over any later model output for
  that field.
- Model, prompt version, and extraction schema version MUST be recorded on every
  AI-derived record. Prompts are versioned artifacts in the repository, not inline
  string literals edited in place.
- No change to a model, prompt, or extraction schema ships without an evaluation run
  against a held-out set of real recordings, with the result recorded. "It looked
  better in a few manual tries" is not an evaluation.
- AI features MUST degrade rather than block: if transcription or extraction is
  unavailable, capture still succeeds and the recording queues for later processing.

TODO(LLMOPS_STACK): the concrete provider, prompt-versioning mechanism, eval harness,
and eval dataset location are undecided. Any chosen stack MUST satisfy the invariants
above; the choices themselves land in a future MINOR amendment.

**Rationale**: An AI-first journal that silently writes wrong facts into a beekeeper's
records is worse than no journal at all, because the beekeeper will trust it and act
on it. Retained source material plus recorded provenance is what makes a wrong output
a fixable annoyance instead of a corrupted season.

### VI. Semantic Versioning & User-Facing Changelog

Versioning is MAJOR.MINOR.PATCH. MAJOR covers backward-incompatible API, schema, or
stored-data-format changes; MINOR covers added capability; PATCH covers fixes and
clarifications. The API is versioned independently of the app, and a released API
version MUST keep serving the clients already in the field — mobile clients update on
the user's schedule, not the server's.

Commit messages follow Conventional Commits and are enforced by commitizen via
pre-commit. Changelog entries describe what changed **for users between releases**:
public API, documented behavior, settings, CLI, dependencies, deprecations. They MUST
NOT describe private names, internal helpers, tests, CI, tooling, docs infrastructure,
or any branch-internal churn. A change introduced and then revised within the same
unreleased cycle is amended or deleted in place, never logged twice.

**Rationale**: Stored inspection data outlives every version of the code that wrote it,
and an app installed on a phone in a rural apiary may go months without updating. The
version number is the contract that makes those two facts survivable.

## Technology Constraints

The baseline stack is fixed; deviations require an amendment.

- **Backend**: Python with FastAPI and Pydantic v2. PostgreSQL is the system of
  record. Schema changes ship as reviewed, forward-tested migrations — never as
  hand-applied SQL or implicit auto-creation.
- **Frontend**: React with TypeScript, delivered as a PWA with IndexedDB for local
  durable storage.
- **Mobile**: Capacitor wrapping the PWA. Platform-specific code is confined to
  explicitly marked adapter modules; the domain layer MUST remain platform-agnostic.
- **AI pipeline**: undecided — see TODO(LLMOPS_STACK) in Principle V. Until decided,
  transcription and extraction MUST sit behind an interface owned by the application,
  so a provider swap does not reach into domain code.

Additional constraints:
- Recordings and inspection notes are personal operational data. They MUST NOT be sent
  to any third-party service that the user has not been told about, and the set of
  external services receiving user content MUST be documented in user-facing terms.
- A dependency is added only when it carries real weight. New runtime dependencies are
  justified in the pull request that introduces them.
- Secrets never enter the repository, and configuration comes from the environment.

## Development Workflow & Quality Gates

- Work happens on branches off `develop`. `main` holds released state.
- Every pull request MUST pass, before merge: `ruff` lint and format, the type checker,
  the full test suite, and the pre-commit hook set (which inserts license headers and
  validates commit messages).
- Every pull request MUST state which principles it touches and, where it deviates,
  justify the deviation in the description. Unjustified complexity is grounds to reject.
- Schema and API changes MUST ship with the corresponding migration, the regenerated
  client types, and tests for both, in the same pull request.
- Changes to prompts, models, or extraction schemas MUST include their evaluation
  result in the pull request description.
- Spec Kit artifacts (`spec.md`, `plan.md`, `tasks.md`) are the planning record for
  non-trivial features; implementation follows the approved plan, and divergence from
  it is written back into the plan rather than left implicit in the code.

## Governance

This constitution supersedes all other development practices for Melliscribe. Where a
tool default, a habit, or a convenience conflicts with a principle here, the principle
wins.

**Amendment procedure**: Amendments are made by editing this file through the
`/speckit-constitution` workflow, in a dedicated commit that states the rationale.
Any amendment that removes or weakens a principle MUST also state what now mitigates
the risk that principle was guarding. An amendment that invalidates existing stored
data or a released API contract MUST include a migration plan before it is ratified.

**Versioning policy**: This document is versioned as MAJOR.MINOR.PATCH.
- MAJOR: a principle is removed, or redefined in a way that makes previously compliant
  work non-compliant.
- MINOR: a principle or section is added, or existing guidance is materially expanded.
- PATCH: clarification, wording, or typo fixes with no change in obligation.

**Compliance review**: Compliance is verified at pull request review — the automated
gates in the workflow section cover what a machine can check, and the reviewer covers
the rest. The constitution is re-read at the start of each planning cycle
(`/speckit-plan`); a principle that has been routinely violated in practice is either
enforced from then on or amended honestly, never left as decoration. Runtime, day-to-day
development guidance lives in `CLAUDE.md`, which MUST NOT contradict this document; if
it does, this document governs and `CLAUDE.md` is corrected.

**Version**: 1.0.0 | **Ratified**: 2026-09-21 | **Last Amended**: 2026-09-21
