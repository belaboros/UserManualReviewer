# COMPARE: Side-by-side comparison of two models

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0010, ADR-0007, ADR-0009
- **Depends on:** RUN, FIND
- **Code:** `src/umr/app/compare.py`, `src/umr/app/matching.py` · **Tests:** [TEST_SPECS/COMPARE-side-by-side-comparison.md](../TEST_SPECS/COMPARE-side-by-side-comparison.md)

## Purpose
The owner wants to see how two LLMs review the same manuals: which problems both found, which only one found, and what each cost. Matching findings by rules (not by eye, not by another LLM) makes agreement, unique catches and likely hallucinations visible at a glance.

## User stories
- As a documentation reviewer, I want to run the same review with model A and model B at the same time, so that I can compare them without waiting twice.
- As a reviewer, I want two saved runs compared, so that I can compare a new model with an older run.
- As a reviewer, I want findings grouped into *found by both*, *only A* and *only B*, so that I can judge each model's unique catches.

## Behaviour

**Inputs**: two `ReviewRun`s (`compare_runs`), or a journey, check ids and two providers (`run_and_compare`).

**Location match** (`umr.app.matching.locations_match`): same page and either overlapping line ranges, or quote similarity ≥ 0.8 (one quote contains the other after whitespace/case normalisation, or rapidfuzz partial ratio ≥ 80). A location with neither lines nor quote stands for the whole page (e.g. an orphan page) and matches any location on that page.

**Finding match** (`findings_match`): at least one location matches; when *both* findings have two or more locations (contradictions), at least two locations must match.

**Pairing** is one-to-one and globally greedy (`pair_best`): all matching pairs are candidates, taken in order of the number of matched locations (higher first), then input order.

| Pass | Candidates |
|---|---|
| 1 | same category and matching findings |
| 2 | remaining findings of any category whose locations match *strongly*: every location of each finding is matched by a location of the other |

**Output** `Comparison(run_a, run_b, both, only_a, only_b)`; `both` holds `(finding of A, finding of B)` tuples in A's order; `only_a`/`only_b` keep each run's order. `agreement` = |both| / (|both| + |only A| + |only B|), 1.0 when both runs are empty. Scores, tokens, cost and duration come from `run_a`/`run_b`.

**Running both**: `run_and_compare` runs the two reviews concurrently in two threads with `ReviewService.review`, sharing one cancel event. Progress events are forwarded as `("A" | "B", ProgressEvent)`. Cancelling, or one side failing, sets the cancel event so the other side stops too; a real error is re-raised, otherwise `ReviewCancelled` is raised. When the service has a `RunStore`, both runs are saved.

```python
CompareService(review: ReviewService | None = None, run_store: RunStore | None = None,
               quote_similarity: float = 0.8)
CompareService.compare_runs(run_a, run_b) -> Comparison
CompareService.run_and_compare(journey, check_ids, provider_a, provider_b, progress=None, cancel=None) -> Comparison
```

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-COMPARE-01 | run A and run B each have a finding of the same category on the same page with overlapping lines | runs are compared | the two findings are one pair in `both` and neither is in `only_a`/`only_b` |
| AC-COMPARE-02 | two same-category findings on the same page without line numbers | runs are compared | they are paired when quote similarity ≥ 0.8, and listed as only A / only B when the quotes differ |
| AC-COMPARE-03 | same-category findings on different pages or non-overlapping lines with different quotes | runs are compared | none are paired |
| AC-COMPARE-04 | findings with different categories | runs are compared | they are paired in the second pass only when all locations of both match; a same-category match is preferred over another category |
| AC-COMPARE-05 | two contradictions with two locations each, of which only one matches | runs are compared | they are not paired; a one-location finding matching one of them is paired |
| AC-COMPARE-06 | two findings in A match the same finding in B | runs are compared | only one pair is formed; the other A finding is in `only_a` |
| AC-COMPARE-07 | a journey, checks and two providers | `run_and_compare` is called | both reviews run at the same time, progress events arrive labelled "A" and "B", and each run records its own model and usage |
| AC-COMPARE-08 | model A reports two findings and model B one matching one of them | `run_and_compare` is called with a `RunStore` | `both` has one pair, `only_a` the other finding, `only_b` is empty, and both runs are saved |
| AC-COMPARE-09 | a running comparison | the cancel event is set | `ReviewCancelled` is raised and both reviews stop |
| AC-COMPARE-10 | one of the two reviews raises an error | `run_and_compare` is called | that error is raised to the caller |

## Examples
A: *contradiction* at `order-capturing/02-creating-an-order.md` lines 57 and `delivery/dispatch.html` line 35 ("cancelled only while … Submitted" vs "cancelled at any time until … Shipped"); B reports *inconsistency* at the same two lines → paired in pass 2. If B instead points at dispatch line 9, only one of two locations matches → only A and only B.

## Out of scope
- Comparing more than two models at once.
- Comparing runs of different journeys or check sets (allowed but not guarded).
- Recall/precision against an answer key (see EVAL).
- The comparison view itself (GUI).

## Open questions
- Should a comparison be saved as its own file, or is saving the two runs enough?
