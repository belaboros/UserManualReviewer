# SCORE: Quality score

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.)
- **Related ADRs:** ADR-0008
- **Depends on:** FIND

## Purpose
One number per set, manual and page: 100% when there are no problems, lower and lower as problems increase.

## Behaviour
`score = 100 × e^(−density / k)`, `density = Σ severity weights / max(words, min_words) × 1000`. Defaults: critical 10, major 5, minor 2, info 0.5, k 20, min_words 300, loaded from `config/scoring.yaml`. Only verified findings count. A finding counts in each manual and page it has a location in; the set score counts all findings.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-SCORE-01 | no verified findings | scores are computed | every score is 100 |
| AC-SCORE-02 | a 1,000-word page with one major finding | scores are computed | the page score is 77.9 |
| AC-SCORE-03 | more or more severe findings | scores are computed | the score is strictly lower, and never below 0 |
| AC-SCORE-04 | a page shorter than min_words | scores are computed | min_words is used as the word count |
| AC-SCORE-05 | a finding with locations in two manuals | scores are computed | it lowers both manual scores and the set score |
| AC-SCORE-06 | an unverified finding | scores are computed | it does not change any score |
| AC-SCORE-07 | a scoring.yaml with other weights and k | it is loaded | those values are used |
