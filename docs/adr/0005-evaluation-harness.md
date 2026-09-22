# ADR-0005: Evaluation harness and dataset layout

**Status**: Accepted
**Date**: 2026-09-21
**Feature**: [001-voice-inspection-capture](../../specs/001-voice-inspection-capture/spec.md)
**Depends on**: [ADR-0001](./0001-two-stage-pipeline.md)

## Context

Principle II is the strictest thing in the constitution: every LLM-based
behaviour ships with an evaluation dataset and automated evals in CI, in the same
pull request, and no prompt, model, vocabulary or schema change merges without a
run. That is a hard gate, and it needs somewhere to live.

Two things make this harder than a generic eval setup. Principle III forbids user
recordings from entering the public repository, so the dataset cannot simply be
committed. And ADR-0001's two stages need separate attribution, so this is two
eval sets, not one.

## Decision

**pytest-driven, in-repo, datasets as JSONL manifests pointing at audio held in
private storage.**

```
backend/evals/
├── harness/              # the runner, invoked identically by CI and by hand
└── datasets/
    ├── transcription.jsonl
    ├── extraction.jsonl
    └── parity.jsonl      # paired fr/en dictations of the same inspection
```

- **The manifest is versioned; the audio is not.** A manifest entry references
  private storage plus either a consent reference or a purpose-made marker, so
  dataset provenance is auditable rather than asserted (FR-027f).
- **Separate gates per stage.** Transcription and extraction have their own
  datasets, thresholds and recorded baselines. A regression blocks the merge for
  the stage it happened in; "the pipeline got worse" is not an actionable result.
- **One entry point**, `melliscribe eval run`, used by CI and by the maintainer,
  so a local run and the gate cannot diverge.
- **Dataset floor**: at least 50 dictations per language, of which at least 20
  are paired. Below that, SC-005 and SC-011 measure noise.

| Metric | Criterion | Gate |
|---|---|---|
| Fields populated from unmentioned content | SC-004 | Zero. Any occurrence fails the build. |
| Confidently-asserted wrong values | SC-003 | Under 15% of corrections |
| French vs English field accuracy | SC-005 | Gap ≤ 5 points |
| Cross-language coded-value agreement | SC-011 | Identical on paired dictations |
| Glossary term recall, per language | SC-010 | ≥ 95% |
| Transcription word error rate, per language | FR-014 | Baseline recorded; regressions block |

## Consequences

**Good.** No new dependency, no new account, no new service. The project already
has pytest, CI and a way to run Python. The harness is reviewable because it is
ordinary test code.

**Costly, and this is the one to watch.** The gate means the first weeks of work
produce nothing a beekeeper can see: a harness, a dataset and a threshold before
a single record exists. **For a solo maintainer with a few hours a week that is
the most likely point of abandonment.** The mitigation is deliberate — front-load
a thin end-to-end path with a *tiny* eval set, then grow the set toward the floor,
rather than building the complete suite before any pipeline code.

**Obligatory.** Assembling the dataset — including recording paired bilingual
dictations by hand, because paired recordings cannot be found — is part of this
feature's work, not a preparatory step someone else does.

## Alternatives considered

**A dedicated eval platform** (promptfoo, Langfuse evals, Braintrust). More
capable, with better reporting and diffing. Rejected under Principle V: another
dependency, another account, another thing to learn, and for two eval sets of
fifty items the reporting is not worth it. Revisit if the sets grow past a few
hundred or a second maintainer appears.

**Committing the audio to the repository.** Would make the dataset trivially
reproducible. Forbidden by Principle III — the repository is public under
AGPL-3.0 and every push is publication.

**One combined eval over the whole pipeline.** Simpler to build and useless when
it fails, for the reasons in ADR-0001.
