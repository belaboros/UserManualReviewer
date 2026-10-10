# ADR-0013: Evaluate LLMs against answer-keyed sample manuals

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
When the owner tries a new LLM (SaaS or local), they want to know how good it is *for this task* before using it on real manuals: does it find the problems, does it invent problems, what does it cost, and how fast is it.

## Decision
An **evaluation** runs a normal review with the chosen model on one or more **benchmark sets** and scores the findings against a machine-readable answer key.

**Benchmark set** = a journey (for example `samples/shopflow/journey.yaml`) plus `expected-findings.yaml`, with one entry per planted problem:
```yaml
- id: C2
  category: contradiction
  severity: major
  locations:
    - { page: order-capturing/02-creating-an-order.md, quote: "can be cancelled only while it has the status" }
    - { page: delivery/dispatch.html, quote: "cancelled at any time until they reach the status" }
  accept_categories: [inconsistency]   # optional: other categories that also count as correct
```

**Matching** reuses the comparison rules of [ADR-0010](0010-side-by-side-comparison.md): a reported finding matches an expected one when their locations overlap (same page and overlapping lines, or quote similarity ≥ 0.8). Each expected finding matches at most one reported finding. For findings with several locations (contradictions), at least two locations must match.

**Metrics**, overall and per category:

| Metric | Meaning |
|---|---|
| Recall | share of planted problems found |
| Precision | share of reported findings that match a planted problem |
| F1 | harmonic mean of recall and precision |
| Category accuracy | matched findings reported in the right (or an accepted) category |
| Severity accuracy | matched findings with the expected severity, ±1 level counts half |
| Verified-quote rate | findings whose quotes exist in the manuals ([ADR-0007](0007-finding-schema-and-verified-quotes.md)) |
| Valid-output rate | LLM calls that returned schema-valid JSON on the first try |
| Stability | with `--repeat N`, the share of expected findings found in every repetition |
| Cost, time, tokens | totals per evaluation run |

**Eval score** (0–100) combines them into one number for ranking: `100 × (0.5 × F1 + 0.2 × verified-quote rate + 0.15 × category accuracy + 0.15 × valid-output rate)`. The weights are in `config/eval.yaml`. Cost and time are shown next to the score, not inside it, so the user can trade quality against price.

**Scope**: only LLM-tier categories are scored by default, because rule checks produce identical results for every model. `--include-rules` evaluates the whole system.

**Unexpected findings** (reported but not in the key) count against precision, but are listed separately: a sample can contain real, unplanted problems. When the owner confirms one, it is added to the key, so the benchmark improves over time. The key file has a `version`, recorded in every result.

**Results** are saved like review runs and shown on a **leaderboard** (GUI view and CLI table) that ranks every evaluated model by eval score, with recall, precision, cost per run and duration, filterable by benchmark version. The CLI is `umr eval --model <name> [--benchmark shopflow] [--repeat 3]`.

## Consequences
- Trying a new model is: add it to `llm-providers.yaml`, run `umr eval`, read the leaderboard.
- The answer key must be maintained with the samples; a sample change without a key change breaks the benchmark, so a test checks that every expected quote still exists in the samples.
- The samples are public and could end up in model training data; more benchmark sets can be added later, including private ones kept outside the repository.
- One benchmark of 68 problems gives a useful but rough signal; repeat runs and more sets make it stronger.

## Alternatives considered
- **LLM-as-judge** to decide whether findings are correct – adds a second model's bias and cost; deterministic matching against a key is reproducible. May be added later only for classifying unexpected findings.
- **Owner rates every finding by hand** – accurate but too slow to repeat for each new model.
- **Public benchmarks** – none measure manual review: contradictions, journey gaps and verified quotes.
