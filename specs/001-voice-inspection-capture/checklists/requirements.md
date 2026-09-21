# Specification Quality Checklist: Voice Inspection Capture

**Purpose**: Validate specification completeness and quality before proceeding to planning
**Created**: 2026-09-21
**Feature**: [spec.md](../spec.md)

## Content Quality

- [x] No implementation details (languages, frameworks, APIs)
- [x] Focused on user value and business needs
- [x] Written for non-technical stakeholders
- [x] All mandatory sections completed

## Requirement Completeness

- [x] No [NEEDS CLARIFICATION] markers remain
- [x] Requirements are testable and unambiguous
- [x] Success criteria are measurable
- [x] Success criteria are technology-agnostic (no implementation details)
- [x] All acceptance scenarios are defined
- [x] Edge cases are identified
- [x] Scope is clearly bounded
- [x] Dependencies and assumptions identified

## Feature Readiness

- [x] All functional requirements have clear acceptance criteria
- [x] User scenarios cover primary flows
- [x] Feature meets measurable outcomes defined in Success Criteria
- [x] No implementation details leak into specification

## Notes

Passed on the second iteration. Two requirements were rewritten after the first
pass failed "testable and unambiguous":

- FR-011 said "enough provenance to reproduce how it was derived", which stated
  an intention rather than a checkable condition. It now names what must be
  stored and why.
- FR-014 said the system must "correctly interpret" domain vocabulary with no
  bar for "correctly". It now binds to the project glossary and to the
  threshold in SC-005.

No [NEEDS CLARIFICATION] markers were raised. Six decisions that the feature
description left open were resolved as documented defaults in the Assumptions
section rather than as blocking questions: hive registry ownership, one hive
per recording, unmatched hive identifiers being parked rather than invented,
review being deferrable, actions to do staying free text, and single-beekeeper
accounts. Each is defensible and each is cheap to reverse at `/speckit-clarify`
if wrong — but three of them move scope, so they are worth a deliberate look
before planning:

1. **Hive registry is out of scope** — this feature assumes hives already
   exist. If they do not, this feature cannot ship alone and needs a registry
   feature ahead of it.
2. **Review is deferrable** — records save unconfirmed. The alternative,
   requiring confirmation at the hive, is defensible for data quality but
   conflicts with Field-First.
3. **Actions to do are free text** — not scheduled or reminder-driven tasks.

Constitution alignment checked against v2.1.0: Field-First (FR-001..FR-004,
FR-024), Evaluation Before Features (SC-003..SC-005 give the eval set its
targets; the Assumptions section makes the eval set part of the work), Privacy
By Default (FR-027), Bilingual By Construction (FR-013, FR-014, FR-025,
FR-026, SC-005), Observability (FR-028), and AI-output-is-a-draft (FR-009,
FR-010, FR-012).

## Re-validation after clarification — 2026-09-21

Five clarifications were integrated; the spec grew from 28 to 45 functional
requirements. Re-checked all 16 items against the updated spec.

**One regression**: "All functional requirements have clear acceptance
criteria" now fails. Two behaviours added during clarification have
requirements but no acceptance scenario in any user story:

- Retention (FR-027a through FR-027f) — the 12-month default, the adjustable
  period, delete-now, expiry warning, and the record outliving its audio.
- Hive creation (FR-015a through FR-015d) — creating a hive by identifier,
  creating one from the review flow, and duplicate identifier rejection.

Both are now real user-facing behaviour with no Given/When/Then covering them.
Either add scenarios to the existing stories or give retention its own story
before `/speckit-plan`.

**Corrections to the notes above**: two of the three flagged scope assumptions
were resolved by clarification and the original text is now stale.

- "Hive registry is out of scope" is no longer true. Minimal hive creation is
  in scope; full apiary management stays out.
- "Review is deferrable" was not asked about and still stands as an assumption
  (FR-024).
- "Actions to do are free text" was confirmed unchanged.

Additionally, clarification resolved a contradiction the first pass missed:
User Story 1 had promised both a finished structured record at the hive and
full offline operation. Offline now guarantees durable capture; the record is
produced when connectivity returns.

## Gap closed — 2026-09-21

The regression above is fixed; all 16 items pass again.

- Hive creation (FR-015a through FR-015d) gained three acceptance scenarios in
  User Story 1, covering creation by identifier, creation from the review flow
  when a dictation names something unknown, and refusal of a duplicate
  identifier.
- Retention (FR-027a through FR-027f) gained its own User Story 4 at P4, with
  seven scenarios covering the 12-month default, changing the period,
  delete-now, the record and transcript surviving the audio, honest reporting
  when playback is no longer possible, warning before expiry, and warning when
  expiry would remove the evidence for still-unconfirmed fields.

Retention is last by priority on purpose: it makes no inspection easier, but
voice capture with no answer to "where does my voice go, and for how long" is
not a product anyone adopts.
