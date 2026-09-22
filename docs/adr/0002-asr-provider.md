# ADR-0002: Speech recognition provider and deployment model

**Status**: **Proposed — blocks all transcription work**
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)
**Depends on**: [ADR-0001](./0001-two-stage-pipeline.md)

## Context

ADR-0001 fixed the shape: a `TranscriptionBackend` interface owned by the
application, turning audio into a timestamped transcript. This ADR picks what
sits behind it.

**This decision is deliberately open.** It cannot be made from a desk, because
the criteria that matter are empirical — French accuracy on real beekeeping
vocabulary is not something a datasheet answers.

## Criteria, in priority order

1. **French and English at parity.** SC-005 allows a 5-point gap. An engine that
   is excellent in English and mediocre in French fails this feature outright,
   whatever else it offers.
2. **Domain vocabulary steering** — keyword boosting, custom vocabulary, or an
   initial prompt. Beekeeping terms are exactly what a general model mangles, and
   SC-010 sets glossary recall at 95% per language.
3. **Segment-level timestamps.** Non-negotiable. FR-023 and the whole of User
   Story 3 depend on playback starting at the passage a field came from. A
   backend that cannot supply timings is disqualified regardless of accuracy.
4. **Privacy posture.** Principle III requires the set of services receiving user
   content to be documented in user-facing terms. A documented processor is
   acceptable; a self-hosted engine removes the disclosure and the egress
   entirely.
5. **Cost at this volume**, which is small — a few dozen recordings of a few
   minutes per beekeeper per week.

## Candidates

Verify current pricing, language performance and timestamp support **at decision
time**. Do not trust remembered figures.

- **Self-hosted Whisper-family** (e.g. `faster-whisper`): no third-party egress,
  no per-minute billing, fixed cost. Requires somewhere to run inference.
- **Hosted APIs** (Deepgram, AssemblyAI, Google, OpenAI): no ops burden, per-
  minute billing, and a disclosure obligation under Principle III.

## Recommendation to test, not to assume

Start self-hosted if the deployment has anywhere to run it. It satisfies
Principle III with no disclosure surface and no metered cost, and a fixed cost
suits a solo maintainer's irregular usage better than per-minute billing. Move to
hosted if the French gap measured on real audio cannot be closed.

## How to decide

A spike, and it does not need the ADR-0005 harness first: record roughly ten
bilingual dictations containing real domain vocabulary — `hausse`, `cadre`,
`essaimage`, `couvain`, and their English equivalents — and run each candidate
against them. Measure word error rate per language, glossary term recall, and
whether usable segment timings come back.

Ten recordings will not settle SC-005. They will settle which candidate is worth
building the full dataset against, which is what this ADR needs.

## Progress — 2026-09-23

**Candidate 1 is built**: self-hosted Whisper through `faster-whisper`
(`pipeline/transcription/faster_whisper.py`, optional extra `asr-local`,
selected with `MELLISCRIBE_ASR_PROVIDER=faster-whisper` and
`MELLISCRIBE_ASR_MODEL`). It is provisional — it exists so a dictation produces
a record end to end while this ADR is open, and it is the first candidate the
spike measures, not the decision.

- Criterion 2: the glossary steers recognition through Whisper's initial prompt,
  in the dictation's language.
- Criterion 3: segment timestamps come back with every segment.
- Criterion 4: audio is transcribed on the Melliscribe server; nothing leaves it.
- The detected language is reported only at 80% confidence or more: on noise
  the detector still names a language, which would raise false mismatch
  warnings (FR-026e).
- Observed on the development machine (CPU, int8, `tiny`): model load plus a
  3-second clip in 9.6 s. No speech accuracy figure yet — that is criterion 1,
  and it needs the recordings.

## Decision

**Not yet made.** Fill this section, set the status to Accepted, and state the
measured figures that justified it.
