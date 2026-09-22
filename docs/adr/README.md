# Architecture Decision Records

Constitution Principle VII: cross-cutting decisions are recorded here. An ADR is
required for any decision that spans components, is expensive to reverse, or
picks between viable alternatives.

ADRs are **append-only**. A reversal is a new ADR that supersedes the old one;
the old one is marked superseded, never edited or deleted. The maintainer of this
project in six months has forgotten why it was built this way, and is the same
person.

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-two-stage-pipeline.md) | Two-stage transcription and extraction pipeline | Accepted |
| [0002](./0002-asr-provider.md) | Speech recognition provider and deployment model | **Proposed — blocks transcription work** |
| [0003](./0003-claude-structured-outputs.md) | Claude with structured outputs for extraction | Accepted |
| [0004](./0004-offline-storage-and-upload-queue.md) | Local storage format and the offline upload queue | Accepted |
| [0005](./0005-evaluation-harness.md) | Evaluation harness and dataset layout | Accepted |
| [0006](./0006-tracing-as-a-table.md) | LLM tracing as a database table | Accepted |

## Format

Each ADR states context, the decision, the alternatives considered, and
consequences. Numbered sequentially. A pull request that makes such a decision
includes its ADR.
