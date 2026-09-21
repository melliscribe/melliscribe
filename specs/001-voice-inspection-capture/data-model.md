# Phase 1 Data Model: Voice Inspection Capture

**Date**: 2026-09-21 | **Plan**: [plan.md](./plan.md) | **Spec**: [spec.md](./spec.md)

Pydantic v2 models are authoritative (Principle IV). Everything here generates
the JSON Schema Claude is constrained to, the OpenAPI schema, and the frontend's
TypeScript types. Database tables mirror these; they do not define them.

New Pydantic base classes added here must be registered in `.ruff.toml` under
`[lint.flake8-type-checking].runtime-evaluated-base-classes`.

---

## Entities

### Hive

The colony. In this feature it is an identifier and nothing else — location,
equipment and lineage belong to apiary management, which is out of scope.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | Server-assigned |
| `identifier` | str | What the beekeeper says out loud. **Unique per account** (FR-015d). Non-empty, trimmed. |
| `created_at` | datetime | |

Never created by the system (FR-015c). Creation is always an explicit beekeeper
action, from the hive list or from the review flow.

---

### Recording

The captured audio. The shortest-lived entity in the system: the transcript and
record it produces both outlive it (FR-027c).

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | **Client-generated at capture time** (FR-006, FR-020). This is the idempotency key for upload and the `custom_id` for batch extraction. |
| `captured_at` | datetime | On the device, at capture |
| `duration_seconds` | float | |
| `language` | `Language` | Copied from the account setting at capture (FR-026) |
| `audio_format` | str | Detected, not assumed (D9) |
| `state` | `RecordingState` | See transitions below |
| `retention_expires_at` | datetime \| None | `captured_at` + retention period; None once audio is gone |
| `audio_available` | bool | False after deletion or expiry (FR-027d) |
| `failure_reason` | str \| None | Populated in `FAILED`; never silently swallowed (FR-019) |

#### RecordingState transitions

```
PENDING_UPLOAD ──> UPLOADED ──> TRANSCRIBING ──> EXTRACTING ──> PROCESSED
      │                              │                │
      │                              └────────────────┴──> FAILED ──┐
      │                                                       ^     │
      └───────────────────────────────────────────────────────┘     │
                        (retry — audio always preserved) <───────────┘
```

`PENDING_UPLOAD` is the offline state and is entered before the UI confirms
success (FR-002). A recording leaves it only on durable server acknowledgement
(FR-003). `FAILED` is terminal only until retried; the audio is never discarded
on failure (FR-019).

Audio deletion is orthogonal to this state machine: it clears `audio_available`
and leaves the record and transcript intact.

---

### Transcript

What was said, retained in full and linked back into the audio so any passage
can be replayed (FR-012, FR-023).

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | |
| `recording_id` | UUID | |
| `full_text` | str | |
| `segments` | list[`TranscriptSegment`] | Ordered, non-overlapping |
| `language_detected` | `Language` \| None | Informational; the account setting governs |

**TranscriptSegment**: `text`, `start_seconds`, `end_seconds`, `confidence`.
Segment timestamps are what make US3's "playback starts at the right passage"
possible; an ASR backend that cannot supply them fails criterion 3 of ADR-0002.

Outlives the audio (FR-027c).

---

### InspectionRecord

The structured outcome of one inspection of one hive.

| Field | Type | Rules |
|---|---|---|
| `id` | UUID | |
| `hive_id` | UUID \| None | None while the hive field is unresolved (FR-015) |
| `recording_id` | UUID | |
| `transcript_id` | UUID | |
| `inspection_date` | date | Defaults to `captured_at`; a spoken date wins (FR-016) |
| `queen_seen` | `ObservationField[QueenSeen]` | |
| `brood` | `ObservationField[BroodState]` | |
| `stores` | `ObservationField[StoresState]` | |
| `temperament` | `ObservationField[Temperament]` | |
| `treatments` | list[`Treatment`] | Never inferred |
| `actions_to_do` | list[`ActionToDo`] | Free text by design |
| `confirmed_at` | datetime \| None | None means unconfirmed — a valid saved state (FR-024) |
| `provenance` | `Provenance` | FR-011 |

Exactly one hive (FR-015). A dictation covering several hives is flagged, never
split silently.

---

### ObservationField

The heart of the model, and where "flagged rather than guessed" actually lives.
Generic over its vocabulary type.

| Field | Type | Rules |
|---|---|---|
| `status` | `FieldStatus` | See below |
| `value` | `T` \| None | **MUST be None unless status is `SYSTEM_DERIVED` or `CONFIRMED`** |
| `verbatim` | str \| None | The phrase it came from (FR-006b) |
| `segment_ref` | `SegmentRef` \| None | Points into the audio for playback (FR-023) |
| `confidence` | float \| None | From extraction; drives the `UNCERTAIN` threshold |

#### FieldStatus

| Status | Meaning | `value` |
|---|---|---|
| `UNKNOWN` | The dictation did not cover this | **Always None.** Zero tolerance (SC-004). |
| `UNCERTAIN` | Heard, but low confidence or unmappable to the vocabulary | May be None, or a best guess **explicitly marked** as needing confirmation (FR-008, FR-006d) |
| `SYSTEM_DERIVED` | Extracted with confidence, not yet confirmed | Set |
| `CONFIRMED` | The beekeeper entered or confirmed it | Set |

**Two invariants worth enforcing in the model itself, not in a service:**

1. `UNKNOWN` with a non-None value is unrepresentable. This is SC-004 — the
   criterion with zero tolerance — and a validator is a cheaper guarantee than
   an eval.
2. A `CONFIRMED` field is never overwritten by later extraction (FR-010),
   including the re-processing triggered by a language correction (FR-026c).

---

### Controlled vocabularies

Language-neutral identifiers with a display label per language (FR-006c). A
French dictation and an equivalent English one store the same value.

```python
class Temperament(StrEnum):
    CALM = "calm"
    NERVOUS = "nervous"
    DEFENSIVE = "defensive"
    AGGRESSIVE = "aggressive"
```

Member keys are CAPITAL_CASED per the team conventions. `QueenSeen`,
`BroodState` and `StoresState` follow the same shape. **The actual members are a
domain decision, not an implementation detail** — the spec's Assumptions call
defining them part of this feature's work, and getting them wrong is expensive
once records exist.

Display labels live in the i18n catalogues, keyed by the identifier. A value
with no label in either language is a CI failure under Principle VIII.

---

### Treatment

| Field | Type | Rules |
|---|---|---|
| `product` | `ObservationField[str]` | Never inferred — regulatory significance |
| `dose` | `ObservationField[str]` | Kept as spoken; not normalised into units here |
| `applied_on` | date \| None | |

Treatments carry harvest-timing and regulatory weight, so the same
flag-don't-guess rule applies with no exceptions. A half-heard product name is
`UNCERTAIN`, never a nearest match.

### ActionToDo

`text` (as phrased), `hive_id`, `created_from_record_id`. Deliberately without a
controlled vocabulary — the space of things a beekeeper decides to come back and
do is not enumerable. Scheduling and reminders are a separate feature.

---

### Provenance

FR-011, and the input to every eval comparison.

| Field | Type |
|---|---|
| `transcription_provider` | str |
| `transcription_model` | str |
| `extraction_model` | str |
| `prompt_version` | str |
| `vocabulary_version` | str |
| `extraction_schema_version` | str |
| `extracted_at` | datetime |

Prompt and vocabulary versions double as part of the prompt-cache key (D5), so
provenance and caching share a version number rather than drifting apart.

---

### LLMTrace

Principle VI. Written by both pipeline stages.

| Field | Type |
|---|---|
| `id` | UUID |
| `recording_id` | UUID |
| `stage` | `TRANSCRIPTION` \| `EXTRACTION` |
| `provider`, `model`, `prompt_version` | str |
| `input_tokens`, `output_tokens`, `cache_read_tokens` | int \| None |
| `cost_usd` | Decimal |
| `latency_ms` | int |
| `outcome` | `SUCCESS` \| `ERROR` \| `TIMEOUT` |
| `fallback_taken` | bool |

`cost_usd` is computed at call time from a rate table carrying the date it was
last checked — a stale rate produces confidently wrong cost reporting, which is
worse than none. `cache_read_tokens` is how D5's caching is verified in
production rather than assumed.

---

## Account-level settings

| Field | Type | Rules |
|---|---|---|
| `language` | `Language` | `FR` or `EN`. Applies to every recording (FR-026). Available offline. Never inferred from network location. |
| `audio_retention_days` | int | Default 365 (FR-027a) |

---

## Entity relationships

```
Account ─┬─< Hive ──────────< InspectionRecord
         │                          │ 1:1
         └─< Recording ──1:1── Transcript
                   │                │
                   └── LLMTrace >───┘

InspectionRecord ──< ObservationField ──> SegmentRef ──> TranscriptSegment
                 ──< Treatment
                 ──< ActionToDo
```

`Recording` is the only entity that can disappear while its neighbours remain.
Every relationship that crosses it — record, transcript, field, trace — is built
to survive its deletion, which is FR-027c stated structurally.
