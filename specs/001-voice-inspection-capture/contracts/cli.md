# CLI Contract

The constitution's Code Standards require every backend library to expose its
core operations through a CLI with a text/JSON protocol: arguments and stdin in,
stdout out, errors to stderr, with a `--json` mode.

This is not ceremony. For this feature the CLI is the cheapest integration test
and the only way to replay a field failure locally — a beekeeper reports a wrong
record, you pull the recording, and you re-run the exact pipeline stage against
it without standing up the API, the PWA, or a browser.

Every command below supports `--json`. Human-readable output is the default.

## `melliscribe transcribe`

```
melliscribe transcribe <audio-file> --language fr|en [--json]
```

Runs only the transcription stage. Prints the transcript with segment
timestamps. Exercises `TranscriptionBackend` with no database and no API.

## `melliscribe extract`

```
melliscribe extract <transcript-file|-> --language fr|en [--json]
                    [--prompt-version V] [--no-cache]
```

Runs only the extraction stage, reading a transcript from a file or stdin.
Prints the record with every field's status, verbatim phrase and segment
reference.

`--prompt-version` runs an older prompt against the same input, which is how a
regression gets attributed. `--no-cache` is for verifying cache behaviour, not
for normal use.

## `melliscribe pipeline`

```
melliscribe pipeline <audio-file> --language fr|en [--json]
```

Both stages end to end, the same path the API takes. This is the replay command.

## `melliscribe vocabulary`

```
melliscribe vocabulary list [--language fr|en] [--json]
melliscribe vocabulary check
```

`check` verifies every controlled-vocabulary value has a display label in both
languages and every glossary term has both forms. It exits non-zero on a gap and
runs in CI as part of the Principle VIII gate.

## `melliscribe retention`

```
melliscribe retention due [--within-days N] [--json]
melliscribe retention apply [--dry-run]
```

`due` lists recordings approaching or past expiry, including which have records
with still-unconfirmed fields — the case that warrants the louder warning
(FR-027e, US4 scenario 7). `apply` performs expiry; `--dry-run` is the default
posture in review.

## `melliscribe eval`

```
melliscribe eval run --dataset <manifest> [--stage transcription|extraction]
melliscribe eval compare <baseline> <candidate>
```

The same entry point CI uses, so a local run and the gate cannot diverge.
`compare` produces the before/after table that goes in the pull request
description (Principle II).

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Success |
| 1 | Operation failed (transcription error, extraction error, eval regression) |
| 2 | Usage error |
| 3 | Missing or unreadable input |
