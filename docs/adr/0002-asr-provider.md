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

## Decision

**Not yet made.** Fill this section, set the status to Accepted, and state the
measured figures that justified it.
