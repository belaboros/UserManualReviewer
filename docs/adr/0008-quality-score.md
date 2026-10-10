# ADR-0008: Quality score with exponential decay over problem density

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The owner wants a quality score for a set of related manuals and for its parts: 100% when everything is perfect, lower and lower as problems increase.

## Decision
```
penalty  = Σ weight(severity) over verified findings in scope
density  = penalty / max(words, min_words) × 1000
score    = 100 × e^(−density / k)
```
Defaults (in `config/scoring.yaml`): weights critical 10, major 5, minor 2, info 0.5; `k` = 20; `min_words` = 300.

Scopes: **page**, **manual** and **set**. A finding counts in every page and manual where it has a location. The set score includes all findings; journey gaps without a location count only there.

Examples on a 1,000-word page: no findings 100%; one minor 90%; one major 78%; four majors 37%; one critical 61%.

## Consequences
- Exactly 100% only with zero verified findings; never negative; always decreasing with more or worse problems.
- Long manuals are not penalised for length; the `min_words` floor keeps tiny pages from dropping to near zero over one issue.
- The score is relative, not absolute truth; weights and `k` are tunable and the run file records which values were used.

## Alternatives considered
- **100 − n × weight, clipped at 0** – hits 0 quickly and stops distinguishing bad from very bad.
- **Raw counts without normalisation** – punishes long manuals.
- **Percentage of sections without issues** – ignores severity and multiple issues in one section.
