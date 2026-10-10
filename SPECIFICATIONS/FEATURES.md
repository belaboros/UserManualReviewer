# Feature list

Ids are permanent. Coverage of every acceptance criterion: [TESTS/traceability.md](../TESTS/traceability.md).

| Id | Feature | Spec | Status |
|---|---|---|---|
| INGEST | Load journeys and manuals (`journey.yaml`, `manual.yaml`, .md, .html) with line mapping | [INGEST](INGEST-load-manuals.md) | Implemented |
| FIND | Finding model, quote verification, de-duplication | [FIND](FIND-findings-and-verification.md) | Implemented |
| LINK | Broken links and anchors, missing images and alt text, orphan pages | [LINK](LINK-links-images-orphans.md) | Implemented |
| DUP | Duplicate and near-duplicate sections | [DUP](DUP-duplicate-sections.md) | Implemented |
| STRUCT | Step numbering that skips or repeats | [STRUCT](STRUCT-step-numbering.md) | Implemented |
| CODE | Malformed code blocks (JSON, YAML, CSV) | [CODE](CODE-malformed-code.md) | Implemented |
| UILABEL | UI labels not matching the reference `ui-strings.json` | [UILABEL](UILABEL-ui-labels.md) | Implemented |
| VERSION | Version mentions that differ from the manual's version | [VERSION](VERSION-stale-versions.md) | Implemented |
| LLM | Provider config file, OpenAI-compatible and Claude adapters, structured output, usage and cost | [LLM](LLM-llm-providers.md) | Implemented |
| PROMPT | Prompt building, context budget and caching layout | [PROMPT](PROMPT-prompt-building.md) | Implemented |
| CONTRA | Contradictions across manuals | [CONTRA](CONTRA-contradictions.md) | Implemented |
| CONSIST | Inconsistencies within one manual, step order logic | [CONSIST](CONSIST-consistency.md) | Implemented |
| JOURNEY | Journey gaps, prerequisite gaps, missing error paths | [JOURNEY](JOURNEY-journey-gaps.md) | Implemented |
| TERM | Terminology drift, undefined terms and acronyms | [TERM](TERM-terminology.md) | Implemented |
| SCORE | Quality score for set, manual and page | [SCORE](SCORE-quality-score.md) | Implemented |
| RUN | Review runs, progress, cancellation, saving, command line | [RUN](RUN-review-runs.md) | Implemented |
| COMPARE | Side-by-side comparison of two models | [COMPARE](COMPARE-side-by-side-comparison.md) | Implemented |
| EVAL | LLM evaluation against an answer key, eval score, leaderboard | [EVAL](EVAL-llm-evaluation.md) | Implemented |
| GUI | Setup, dashboard, findings, finding detail, compare, evaluate, leaderboard | [GUI](GUI-desktop-app.md) | Implemented |

"Implemented" means built and tested; all specs were approved by the owner's go-ahead on 2026-10-10 and are being validated in owner testing.
