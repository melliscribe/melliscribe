# ADR-0004: Local storage format and the offline upload queue

**Status**: Accepted
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)

## Context

Principle I treats offline as the normal operating condition. An apiary has no
signal and the app must behave as though it never will. Two requirements make
this concrete and they are stricter than they look:

- FR-002: a recording is durably persisted **before** the UI confirms success.
- FR-003: locally held data is **not discarded** until the server acknowledges
  durable receipt.

Together these forbid the ordinary pattern of optimistically uploading and
showing a spinner. The confirmation a beekeeper sees when they close a hive has
to mean something, because a lost inspection cannot be reconstructed — the hive
is closed and they have moved on.

Clarification settled what offline actually promises: durable capture, not a
finished record. The record is produced when connectivity returns.

## Decision

**IndexedDB**, accessed through a thin application-owned wrapper, with audio
blobs and the pending-operations queue in **separate object stores**.

- Every recording gets a **client-generated UUID at capture time**. This is the
  idempotency key for upload (FR-020) and the `custom_id` for batch extraction
  (ADR-0003). One identifier, generated where the data is born.
- The queue holds **explicit state** per recording, not implicit intent. A
  recording leaves `PENDING_UPLOAD` only on a `201` or `200` from the server.
- Upload is attempted **opportunistically in the foreground** with backoff.
  **Background Sync is an optimisation, never the guarantee** — it is not
  available everywhere and not reliable enough to be the only path.
- Storage pressure is surfaced before it bites (FR-021).

**No conflict resolution.** A recording is written once by one device and never
edited concurrently. The client-generated id makes upload idempotent, and that
is the entire sync story for this feature.

## Consequences

**Good.** The confirmation the beekeeper sees is truthful. A retried upload
cannot duplicate an inspection. The queue is inspectable, which is what FR-018
("show me what is pending and what failed") needs.

**Costly.** Audio in IndexedDB competes with everything else on the device for
quota, and quota behaviour differs across browsers. Eviction under pressure is a
real risk on the one path that must not lose data, which is why FR-021 warns
early rather than cleaning up quietly.

**Deliberately absent.** No conflict resolution, no vector clocks, no merge
strategy. Principle V forbids building for a concurrency model that does not
exist yet. **The moment records become editable from two devices, this ADR is
superseded** — that is the trigger to watch for, and it is a new ADR rather than
an extension of this one.

## Alternatives considered

**Optimistic upload with local cache as a convenience.** The common pattern.
Rejected outright: it violates FR-002 and FR-003, and the failure mode is exactly
the one this product cannot have.

**Background Sync as the primary mechanism.** Rejected as the *guarantee*, kept
as an optimisation. Availability is uneven and the beekeeper's data does not get
to depend on a best-effort browser API.

**A sync framework with conflict resolution built in.** Rejected under Principle
V. It solves a problem this feature does not have, at the cost of a large
dependency on the most safety-critical path in the app.

**Server-generated ids.** Rejected: the id has to exist before the device has
ever spoken to the server, or the offline path has nothing to key on.
