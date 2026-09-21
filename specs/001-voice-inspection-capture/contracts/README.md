# Contracts: Voice Inspection Capture

Three interfaces, all generated from or checked against the Pydantic v2 models
in [data-model.md](../data-model.md).

| Contract | File | Consumer |
|---|---|---|
| HTTP API | [api.md](./api.md) | The PWA, via generated TypeScript types |
| Extraction | [extraction.md](./extraction.md) | Claude, via `output_config.format` |
| CLI | [cli.md](./cli.md) | The maintainer, and integration tests |

**The generation chain** (Principle IV). One definition, three consumers:

```
Pydantic v2 model
   ├──> JSON Schema ──> output_config.format ──> Claude's constrained output
   ├──> OpenAPI ──> openapi-typescript ──> frontend/src/api/generated/
   └──> the CLI's --json output shape
```

CI fails if the committed generated types differ from what the current schema
produces. Hand-written TypeScript that mirrors a backend model is forbidden.
