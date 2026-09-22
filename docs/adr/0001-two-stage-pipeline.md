# ADR-0001: Two-stage transcription and extraction pipeline

**Status**: Accepted
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)

## Context

A beekeeper speaks an inspection and expects a structured record. Something has
to turn speech into a record, and the obvious question is whether that is one
step or two.

Claude has no speech-to-text input. That settles the mechanical question — audio
cannot go directly to the model producing the record — but it does not by itself
settle the architecture, because a single multimodal provider handling audio
straight to structured output is a real option with other vendors.

The deciding constraint is Principle II. Every LLM behaviour ships with an
evaluation, and an evaluation that cannot attribute a failure is not much of an
evaluation. When a record comes back wrong there are two very different causes:
the audio was misheard, or the transcript was misread. "Hausse" transcribed as
"housse" is a recognition failure. A correct transcript coded to the wrong
temperament is a reasoning failure. They are fixed in different places — a
custom vocabulary versus a prompt — and conflating them means every regression
investigation starts from scratch.

## Decision

Transcription and extraction are **separate stages with separate providers,
separate interfaces, separate evaluation datasets, and separate pass gates.**

```
audio ──> TranscriptionBackend ──> Transcript ──> Extractor ──> InspectionRecord
              (ADR-0002)          (timestamped)   (ADR-0003)
```

Both stages sit behind interfaces owned by the application, so neither provider
choice reaches into domain code. Both write a trace row (ADR-0006). A failure
records which stage produced it (FR-019b), and a transcript that succeeded is
never recomputed because extraction failed (FR-019a).

## Consequences

**Good.** Failures are attributable, which is what makes the eval gate
actionable rather than decorative. The transcript becomes a first-class artifact
the beekeeper can be shown (FR-006b) and which outlives the audio (FR-027c). The
stages can be retried, re-run and re-evaluated independently, and a provider on
either side can be swapped without touching the other.

**Costly.** Two providers to configure, two interfaces to maintain, two eval
datasets to build, and two sets of failure modes. For a solo maintainer that is
real overhead, and it is the price of attribution.

**Structural.** The record keeps a reference to the transcript and, through it,
into positions in the audio. That chain is what US3 is built on; a merged
pipeline would have had no intermediate artifact to point at.

## Alternatives considered

**Single multimodal audio-to-record call.** One provider, one prompt, one
request. Rejected: a wrong record is uninvestigable, there is no transcript to
show the beekeeper under FR-006b or to replay under FR-023, and nothing survives
the audio's deletion. It optimises for the happy path of a feature whose entire
value proposition is behaving well when it is unsure.

**Two stages, one provider.** Using one vendor for both, if one offered both.
Not rejected on principle — it would still be two stages behind two interfaces,
which is what this ADR actually requires. The interfaces are what matter; vendor
consolidation is ADR-0002's business.
