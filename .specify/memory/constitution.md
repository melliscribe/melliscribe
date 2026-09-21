# Melliscribe Constitution

Melliscribe is an AI-first apiary management application. A beekeeper speaks at
the hive — gloves on, hands full, often with no signal — and the system turns
that speech into a structured record of colony state, actions performed, and
actions still to do.

It is open source under AGPL-3.0 and built by a single maintainer with a few
hours a week. Both facts are constitutional: the principles below are chosen to
be enforceable by automation rather than by review capacity, and to keep a
public repository safe to publish from a private apiary.

## Core Principles

### I. Field-First

A feature that cannot be used in an apiary does not count as delivered. The
operating environment is assumed hostile: gloved hands, bright sunlight, one
hand occupied by a frame, and no network.

- Every user-facing flow MUST be completable by voice. Touch is a fallback, not
  the primary path.
- Touch targets that remain MUST be operable with beekeeping gloves — large,
  widely spaced, and tolerant of imprecise taps. No hover-dependent or
  long-press-only interactions on a critical path.
- Capture MUST succeed with no network. Audio, structured edits, and notes are
  written to durable local storage before any UI confirms success.
- Locally captured data MUST NOT be discarded until the server acknowledges
  durable receipt. Upload failures retry; they never drop.
- Every record carries a client-generated stable identifier and a logical
  timestamp, so that sync is idempotent and a retried upload cannot duplicate
  an inspection.
- Conflict resolution MUST be explicit and documented per entity type. Silent
  last-write-wins over field notes is forbidden; unresolvable conflicts surface
  to the user with both versions intact.
- Network-dependent behavior MUST degrade rather than block.

**Rationale**: A lost or unenterable inspection cannot be reconstructed — the
hive is closed and the beekeeper has moved on. Every compromise here is paid
for months later with a gap in the season's record.

### II. Evaluation Before Features

No LLM-based behavior ships without a way to tell whether it got better or
worse.

- Every LLM-based behavior MUST ship together with an evaluation dataset and
  automated evals that run in CI. The evals land in the same pull request as
  the behavior, not afterwards.
- No change to a prompt, model, or extraction schema merges without an eval run
  on the affected dataset, with the result visible in the pull request. "It
  looked better in a few manual tries" is not an evaluation.
- A regression against the recorded baseline blocks the merge unless the
  trade-off is stated explicitly and accepted in writing.
- Prompts are versioned artifacts in the repository, not inline string literals
  edited in place. Model, prompt version, and extraction schema version MUST be
  recorded on every AI-derived record.
- AI output is a draft, never the record. Raw transcripts remain retrievable
  alongside anything derived from them; every AI-derived field is visibly
  marked as such and is editable; a user edit permanently wins over any later
  model output for that field.

**Rationale**: LLM behavior degrades invisibly. Without an eval gate the only
detector is a beekeeper noticing that their logbook has been quietly wrong for
a month — and by then the training data for a fix is gone.

### III. Privacy By Default

The repository is public. The beekeeper's data is not.

- Raw audio, personal recordings, transcripts of real inspections, and private
  eval data MUST NEVER enter the public repository, in any commit, on any
  branch, including as test fixtures.
- Evaluation datasets that contain real user recordings stay in private
  storage. The repository holds the eval harness, the schema, and synthetic or
  explicitly-consented fixtures; it references private data by pointer.
- User content MUST NOT be sent to any third-party service the user has not
  been told about. The set of external services that receive user content MUST
  be documented in user-facing terms.
- Secrets never enter the repository. Configuration comes from the environment.
- A leak of this kind is treated as an incident: rotate what is exposed, purge
  the history, and record what happened.

**Rationale**: AGPL-3.0 means every push is publication. A private recording
committed once is public permanently, and no later commit can retract it.

### IV. Single Source Of Truth For Data

Each piece of schema is defined exactly once, and everything else is generated
from it.

- Pydantic v2 models are the authoritative definition of every domain entity
  and every API payload.
- TypeScript types MUST be generated from the OpenAPI schema the backend emits.
  Hand-written TypeScript interfaces that mirror a backend model are forbidden.
- Generation MUST run in CI, and CI MUST fail if the committed generated types
  differ from what the current schema produces.
- Database schema changes ship as reviewed, forward-tested migrations — never
  as hand-applied SQL or implicit auto-creation.

**Rationale**: A solo maintainer cannot hold two definitions of the same thing
in sync by discipline across weeks of interrupted work. Drift between backend
and frontend types is the failure that a generator makes structurally
impossible.

### V. Simplicity

Build the smallest thing that a beekeeper can actually use in the field, then
the next one.

- Every increment MUST be independently usable in the field. Work that is only
  valuable once a later increment lands does not ship on its own.
- Speculative abstractions are forbidden. An abstraction is introduced at the
  second concrete use, not in anticipation of one.
- Prefer boring, well-documented technology with a large community over novel
  or clever technology. When two options are comparable, the more boring one
  wins by default.
- A new runtime dependency MUST be justified in the pull request that
  introduces it.
- Complexity that cannot be justified in a sentence is removed, not documented.

**Rationale**: The budget is a few hours a week, spread thin and interrupted.
Every abstraction built for an imagined future is paid for out of the same hours
that were supposed to build the real one, and every clever dependency becomes an
unpaid maintenance debt the moment its author moves on.

### VI. Observability

Every LLM call MUST be traced.

- Each call records, at minimum: model, prompt version, input and output token
  counts, computed cost, latency, and outcome (success, error, timeout).
- Traces MUST be queryable in aggregate, so cost per inspection and latency
  percentiles are answerable without instrumenting a one-off script.
- Trace payloads containing user content fall under Principle III: they live in
  private storage, never in the repository.
- Errors and timeouts are recorded, not swallowed. A silent fallback path MUST
  emit a trace marking that it was taken.

**Rationale**: Cost and latency are the two failure modes that a side project
discovers too late — one by way of a bill, the other by way of a beekeeper
giving up on a spinner in the sun. Both are invisible without per-call
instrumentation from the start.

### VII. Architecture Decisions Are Recorded

Cross-cutting decisions MUST be recorded as Architecture Decision Records in
`docs/adr/`.

- An ADR is required for any decision that spans components, is expensive to
  reverse, or picks between viable alternatives: transcription and LLM provider
  choice, sync and conflict-resolution strategy, local storage format,
  authentication model, the eval harness, and the tracing backend.
- Each ADR states context, the decision, the alternatives considered, and
  consequences. ADRs are numbered sequentially and are append-only: a reversal
  is a new ADR that supersedes the old one, which is marked superseded rather
  than edited or deleted.
- A pull request that makes such a decision MUST include its ADR.

**Rationale**: The maintainer of this project in six months has forgotten why
this one was built this way, and is the same person. An ADR is the only cheap
defense against relitigating a settled decision — or worse, silently reversing
it.

## Project Context

- **License**: AGPL-3.0. The repository is public and every push is
  publication.
- **Team**: one maintainer, a few hours per week, with gaps of weeks between
  sessions. Governance that depends on a second reviewer does not work here;
  where a rule must be enforced, it is enforced by CI.
- **Users**: beekeepers recording inspections in the field, whose data is
  personal operational data and often irreplaceable.

## Technology Constraints

The baseline stack is fixed; deviations require an ADR under Principle VII.

- **Backend**: Python with FastAPI and Pydantic v2. PostgreSQL is the system of
  record.
- **Frontend**: React with TypeScript, delivered as a PWA with IndexedDB for
  local durable storage.
- **Mobile**: Capacitor wrapping the PWA. Platform-specific code is confined to
  explicitly marked adapter modules; the domain layer stays platform-agnostic.
- **AI pipeline**: provider undecided. Transcription and extraction MUST sit
  behind an interface owned by the application, so a provider swap does not
  reach into domain code. The choice, when made, lands as an ADR.

## Code Standards

**Structure**: Domain logic (colony state transitions, inspection parsing,
audio handling, sync reconciliation) MUST NOT live in FastAPI route handlers or
React components; those layers are adapters and stay thin. Backend capabilities
are implemented as independently testable libraries, and each exposes its core
operations through a CLI with a text/JSON protocol — arguments and stdin in,
stdout out, errors to stderr, with a `--json` mode. A CLI is the cheapest
integration test and the fastest way to replay a field failure locally.

**Python**: All sources begin with `from __future__ import annotations` and
carry type hints on every public signature. `ruff` lint and format and the type
checker MUST pass with zero unjustified suppressions. Imports are single-line
(`force-single-line = true`). Docstrings follow the Google convention in
mkdocs/markdown syntax — `[ClassName][module.ClassName]`, never Sphinx RST —
with an `Args:` section whenever the callable takes parameters beyond
`self`/`cls` and a `Returns:` section whenever it returns a non-`None` value,
private and `@staticmethod` callables included. Callables are named starting
with a verb; noun-only names are reserved for attributes and properties. Enum
member keys are CAPITAL_CASED. License headers are required on all source
files.

**TypeScript**: `strict` mode. `any` requires a written justification at the use
site.

## Development Workflow & Quality Gates

- Work happens on branches off `develop`. `main` holds released state.
- **Test-first**: tests are written before the implementation, observed to fail,
  and only then made to pass. Library contracts, API contracts, offline-to-online
  sync paths, and database migrations MUST have tests before the code exists. A
  bug fix begins with a failing regression test. A pull request that adds
  behavior with no test that would have failed beforehand MUST NOT merge.
- **CI gates**, all blocking: `ruff` lint and format, the type checker, the full
  test suite, pre-commit hooks, generated-type drift (Principle IV), and evals
  for any touched LLM behavior (Principle II).
- Schema and API changes ship with the migration, the regenerated client types,
  and tests for all of it, in the same pull request.
- Changes to prompts, models, or extraction schemas include their eval result in
  the pull request description.
- Cross-cutting decisions ship with their ADR (Principle VII).
- **Releases**: MAJOR.MINOR.PATCH. The API is versioned independently of the
  app, and a released API version keeps serving clients already in the field —
  phones update on the user's schedule, not the server's. Commits follow
  Conventional Commits, enforced by commitizen. Changelog entries describe what
  changed for users between releases — public API, documented behavior,
  settings, CLI, dependencies, deprecations — and never internal names, tests,
  CI, tooling, or branch-internal churn.
- Spec Kit artifacts (`spec.md`, `plan.md`, `tasks.md`) are the planning record
  for non-trivial features. Divergence from an approved plan is written back
  into the plan, not left implicit in the code.

## Governance

This constitution supersedes all other development practices for Melliscribe.
Where a tool default, a habit, or a convenience conflicts with a principle here,
the principle wins.

**Amendment procedure**: Amendments are made through the `/speckit-constitution`
workflow, in a dedicated commit whose message states the rationale. An amendment
that removes or weakens a principle MUST state what now mitigates the risk that
principle was guarding. An amendment that invalidates stored data or a released
API contract MUST include a migration plan before it is ratified. Because there
is a single maintainer, amendments are self-approved — the written rationale is
the accountability mechanism, and it is not optional.

**Versioning policy**: MAJOR.MINOR.PATCH.
- MAJOR: a principle is removed, or redefined such that previously compliant
  work becomes non-compliant.
- MINOR: a principle or section is added, or guidance is materially expanded.
- PATCH: clarification, wording, or typo fixes with no change in obligation.

**Compliance review**: Enforcement is automated wherever a machine can do it —
see the CI gates above — because review capacity is the scarcest resource in
this project. What cannot be automated is checked at the start of each planning
cycle (`/speckit-plan`), when this document is re-read. A principle that is
routinely violated in practice is either enforced from that point on or amended
honestly; it is never left standing as decoration. Runtime, day-to-day
development guidance lives in `CLAUDE.md`, which MUST NOT contradict this
document; if it does, this document governs and `CLAUDE.md` is corrected.

**Version**: 2.0.0 | **Ratified**: 2026-09-21 | **Last Amended**: 2026-09-21
