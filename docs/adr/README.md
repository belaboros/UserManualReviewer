# Architecture decision records

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-architecture-decisions.md) | Record architecture decisions as ADRs | Proposed |
| [0002](0002-python-and-pyside6.md) | Python with PySide6 for a desktop application | Proposed |
| [0003](0003-llm-access-openai-compatible-plus-native-claude.md) | OpenAI-compatible API as the standard, plus an optional native Claude adapter | Proposed |
| [0004](0004-llm-provider-config-file.md) | LLM providers in a YAML config file, keys in environment variables | Proposed |
| [0005](0005-manual-and-journey-format.md) | Manuals are folders with `manual.yaml`; a journey is a `journey.yaml` | Proposed |
| [0006](0006-two-tier-checks.md) | Two tiers of checks, rule-based and LLM-based | Proposed |
| [0007](0007-finding-schema-and-verified-quotes.md) | One finding schema, with quotes verified against the source | Proposed |
| [0008](0008-quality-score.md) | Quality score with exponential decay over problem density | Proposed |
| [0009](0009-review-runs-as-json-files.md) | Store review runs as JSON files | Proposed |
| [0010](0010-side-by-side-comparison.md) | Compare two models by matching findings | Proposed |
| [0011](0011-testing-strategy.md) | Test with a fake LLM, recorded responses and an answer key | Proposed |
| [0012](0012-specification-driven-development.md) | Specification-driven development with traceable acceptance criteria | Proposed |
| [0013](0013-llm-evaluation-benchmark.md) | Evaluate LLMs against answer-keyed sample manuals | Proposed |

New ADRs use [template.md](template.md).
