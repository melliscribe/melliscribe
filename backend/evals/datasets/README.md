# Evaluation datasets

Manifests for the evaluation gate (constitution Principle II, ADR-0005). One
JSON object per line. `melliscribe eval run --dataset datasets/<name>.jsonl`
runs every stage present in a manifest; CI runs the same command.

## The rule that matters: no user audio here

This repository is public (AGPL-3.0). **Audio, and transcripts of real
inspections, never enter it** — not as fixtures, not on a branch
(Principle III). A manifest *points at* private storage: every `audio_ref` and
`transcript_ref` is a path relative to `MELLISCRIBE_EVAL_STORAGE` (default
`~/.melliscribe/evals`), which lives outside the repository.

The one exception is **synthetic** material: a transcript written for the
purpose, describing no real inspection, may be held inline as `segments`.
`smoke.jsonl` is entirely synthetic.

## Provenance is audited, not asserted (FR-027f)

Every case carries one of:

- `"consent_ref": "<id>"` — the consent record of the recording it came from,
  given explicitly and separately by the beekeeper, with its date; or
- `"purpose_made": true` — recorded or written for evaluation, containing no
  beekeeper's data.

A case with neither fails to load, so a dataset without auditable provenance
cannot run.

## Case shapes

Common fields: `id`, `stage`, `language` (`fr` | `en`), optional `pair_id`
(cases sharing one are the same inspection dictated in each language — needed
for SC-005 and SC-011, and purpose-made by necessity), and the provenance field
above.

### `"stage": "extraction"`

| Field | Meaning |
|---|---|
| `captured_on` | The capture day, ISO date |
| `hives` | The beekeeper's hive identifiers at the time |
| `segments` *or* `transcript_ref` | Inline synthetic segments, or a transcript JSON in private storage |
| `expected.is_inspection` | Whether a record should be produced (FR-016b) |
| `expected.fields.<name>` | `{"status": ..., "value": ...}` for `hive` (identifier), `inspection_date` (ISO), `queen_seen`, `brood`, `brood_pattern`, `stores`, `temperament`, and the counts `brood_frames`, `stores_frames`, `bee_frames` (a number in frames, e.g. `"5"` or `"3.5"`). Omit a field to leave it unscored. |

A field is accurate only when status **and** value match (SC-005). A field
expected `unknown` that comes back with a value or a proposal is an SC-004
violation and fails the build.

### `"stage": "transcription"`

| Field | Meaning |
|---|---|
| `audio_ref` | Audio file in private storage |
| `audio_format` | Its media type |
| `reference_text` | What was actually said |
| `glossary_terms` | Glossary terms spoken, in the case's language (SC-010) |

## Datasets

| File | Purpose | Size |
|---|---|---|
| `smoke.jsonl` | Thin CI gate while the pipeline is built (ADR-0005 mitigation) | 32 synthetic extraction cases, 16 pairs |
| `extraction.jsonl`, `transcription.jsonl`, `parity.jsonl` | The full gate that closes US1 (T093) | ≥50 per language, ≥20 paired — **to be assembled** |

The maintainer appends the ADR-0002 spike recordings (T009) to `smoke.jsonl` as
transcription cases once they are in private storage.

## Baselines

`evals/baselines/<dataset>.<stage>.json` holds the recorded baseline. Write one
with `--output`, review it, and commit it. A regression beyond the tolerance in
`melliscribe.evals.gates` blocks the merge unless the trade-off is accepted in
writing in the pull request.
