# HTTP API Contract

All payloads are Pydantic v2 models; the OpenAPI schema is generated from them
and the frontend's types are generated from that. Shapes below name the model
rather than restating it.

All endpoints are scoped to the authenticated beekeeper. Authentication itself
is out of scope for this feature.

## Recordings

### `POST /recordings`

Upload a captured recording. **Idempotent on the client-generated `id`** — a
repeat of the same id returns the existing recording rather than creating a
second (FR-020).

Multipart: `id` (UUID, client-generated), `captured_at`, `duration_seconds`,
`language`, `audio_format`, `audio` (blob).

- `201` — accepted, durably stored. **Only this response permits the client to
  drop its local copy** (FR-003).
- `200` — already held, same id. Also permits dropping the local copy.
- `415` — unsupported audio format. The client keeps the file (FR-005 edge case).
- `413` — too large.

### `GET /recordings`

The beekeeper's recordings with their state, including what is queued and what
has failed (FR-018). Filterable by `state`.

### `GET /recordings/{id}/audio`

Streams the audio, range requests supported for per-field playback (FR-023).

- `410 Gone` — deleted or aged out. **The client must render this as "no longer
  kept", not as a broken control** (FR-027d).

### `DELETE /recordings/{id}`

Deletes the audio immediately, whatever the retention setting (FR-027b). The
inspection record and transcript are untouched (FR-027c).

- `204` — audio gone, record intact.

### `POST /recordings/{id}/retry`

Re-queues a failed recording. The audio is preserved across failures (FR-019).

### `POST /recordings/{id}/reprocess`

Re-runs the pipeline, optionally against a corrected `language` (FR-026b).
**Fields already `CONFIRMED` are preserved** (FR-026c) — the server merges
rather than replaces.

## Inspection records

### `GET /records` · `GET /records/{id}`

`GET /records` filters by `hive_id`, `confirmed`, and date range. Each
`ObservationField` carries its status, verbatim phrase and segment reference, so
the review UI needs no second call to show provenance.

### `PATCH /records/{id}`

Correct or confirm fields. Any field set here becomes `CONFIRMED` and is
permanently immune to later extraction (FR-010).

- `409` — the record was re-processed concurrently; the client refetches.

### `POST /records/{id}/confirm`

Confirms the record as a whole. Not required for the record to be saved —
unconfirmed is a valid resting state (FR-024).

## Hives

### `GET /hives` · `POST /hives`

`POST` takes `identifier` and nothing else (FR-015a).

- `201` — created.
- `409` — identifier already in use. **The server refuses; it does not
  disambiguate silently** (FR-015d).

### `POST /records/{id}/resolve-hive`

Resolves a flagged hive field, either by naming an existing `hive_id` or by
supplying an `identifier` to create (FR-015b). Creation here is still an
explicit beekeeper action, so FR-015c holds.

## Settings

### `GET /settings` · `PATCH /settings`

`language` (`fr` | `en`) and `audio_retention_days`. The language applies to
every subsequent recording; it is never inferred from request origin (FR-026).

## Error shape

A single Pydantic error model across every endpoint, carrying a machine-readable
`code` and a **message localised to the account language** — API error messages
are user-facing text and fall under Principle VIII (FR-025).
