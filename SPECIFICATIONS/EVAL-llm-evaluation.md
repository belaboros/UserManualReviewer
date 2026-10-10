# EVAL: LLM evaluation against an answer key

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0013, ADR-0010, ADR-0011, ADR-0007, ADR-0009
- **Depends on:** RUN, FIND, COMPARE (matching rules)
- **Code:** `src/umr/app/evaluation.py`, `src/umr/storage/evals.py`, `samples/shopflow/expected-findings.yaml` · **Tests:** [TESTS/EVAL-llm-evaluation.md](../TESTS/EVAL-llm-evaluation.md)

## Purpose
When the owner tries a new LLM, they want one trustworthy answer to "how good is this model at reviewing manuals, and what does it cost?" The evaluation runs a normal review on a benchmark set whose planted problems are known, matches the findings to the answer key deterministically, and reports metrics, an eval score and a leaderboard.

## User stories
- As the owner, I want to evaluate a model from `llm-providers.yaml` on the ShopFlow benchmark, so that I know its recall, precision, cost and time before using it.
- As the owner, I want repeated runs and a stability figure, so that I know whether a model's results are reproducible.
- As the owner, I want a leaderboard of all evaluated models, so that I can pick the best model for the price.
- As a maintainer, I want a test that fails when a sample manual changes but the key does not.

## Behaviour

### Benchmark sets and answer key
`config/eval.yaml` lists benchmarks (`name → journey, answer_key`, paths relative to the repository root), the eval score weights and the quote similarity. An answer key (`AnswerKey`) has `version`, `benchmark` and `findings`; each `ExpectedFinding` has `id`, `category`, `severity`, `title`, `locations` (`page` = `<manual_id>/<page_path>`, verbatim `quote`), optional `accept_categories` and `tier` (`llm` default, or `rule`).

`samples/shopflow/expected-findings.yaml` (version "1") holds the 68 distinct planted problems of `ANSWER_KEY.md` (entries marked "same as" are merged; 45 `llm`, 23 `rule`). Quotes are 5–15 words of readable text where the page allows it; image entries quote the image path, headings and table rows are short.

### Matching (ADR-0013)
1. Each expected quote is located in the benchmark journey with `umr.app.verify.locate_quote` to get line numbers.
2. A reported finding matches an expected one by the COMPARE location rules (same page and overlapping lines, or quote similarity ≥ 0.8; when both have ≥ 2 locations, ≥ 2 must match). **Category is ignored** for matching.
3. Pairing is one-to-one, globally greedy by number of matched locations; ties prefer the exact category, then an accepted category, then key order.

### Scope
By default only expected findings with `tier: llm` and reported findings from LLM-tier checks count (tier from `CheckRegistry`, else `source != "rule"` means LLM), and `evaluate` runs only the LLM checks. `include_rules=True` counts everything and runs all checks.

### Metrics (per run)
| Metric | Definition |
|---|---|
| recall | matched expected / expected (1.0 when nothing is expected) |
| precision | matched reported / reported (when nothing is reported: 1.0 if nothing expected, else 0.0) |
| F1 | 2PR / (P + R), 0 when both are 0 |
| category accuracy | matched pairs whose reported category is the expected or an accepted one / matched pairs (0 with no pairs) |
| severity accuracy | mean over matched pairs: exact = 1, one level off in `SEVERITY_ORDER` = 0.5, else 0 (0 with no pairs) |
| verified-quote rate | verified reported findings / reported (0 with none reported) |
| valid-output rate | `ReviewRun.llm_stats.valid_output_rate` |
| per category | one row per category in the expected or reported set: expected, found (matched expected of that category), reported (reported in that category), recall, precision (matched reported in that category / reported), F1 |

**Repeats**: with `repeat = N`, each run is scored and the metrics (and per-category rates) are averaged; per-category counts are rounded means. **Stability** (N ≥ 2) = share of in-scope expected findings found in every run; `None` for one run. `missed`, `unexpected` and `matched` (`(expected id, finding id)`) come from the last run. `usage` is the sum over runs, `duration_s` the sum of run wall times.

**Eval score** = round(100 × Σ weight × metric, 1) over the weights in `config/eval.yaml` (`f1` 0.50, `verified_quote_rate` 0.20, `category_accuracy` 0.15, `valid_output_rate` 0.15).

### Saving and leaderboard
`evaluate` saves each review run with `RunStore` and the `EvalResult` with `EvalStore` (`~/.user-manual-reviewer/evals/<timestamp>-<benchmark>-<model>-<id>.json`, or `$UMR_EVALS_DIR`). `score_runs` makes no LLM calls and saves nothing. `EvalStore.load_all()` returns readable results oldest first and skips broken files. `leaderboard(results)` keeps the latest result per (model, benchmark, key version) and sorts by eval score, best first.

```python
EvalService(config_path=Path("config/eval.yaml"), review=None, store=None, repo_root=None, run_store=None)
EvalService.benchmarks() -> list[str]
EvalService.evaluate(provider, benchmark="shopflow", repeat=1, include_rules=False, progress=None, cancel=None) -> EvalResult
EvalService.score_runs(runs, benchmark="shopflow", include_rules=False) -> EvalResult
leaderboard(results) -> list[EvalResult]
EvalStore(root=None).save(result) -> Path / .load_all() -> list[EvalResult]
```

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-EVAL-01 | an answer key YAML file | `AnswerKey.load` is called | it is parsed with `tier` defaulting to `llm` and `accept_categories` to empty; an unknown category is rejected |
| AC-EVAL-02 | reported findings at the expected locations with an accepted and a wrong category | the run is scored | both are matched; category accuracy counts only the accepted one; on a tie the exact category wins |
| AC-EVAL-03 | a run with two of four in-scope expected findings and one unexpected finding | the run is scored | recall 0.5, precision 2/3, F1 accordingly; per-category rows give expected/found/reported, recall and precision; missed and unexpected are listed; an empty run scores 0 |
| AC-EVAL-04 | matched findings with exact, one-level-off and two-level-off severity | the run is scored | severity accuracy is the mean of 1, 0.5 and 0 |
| AC-EVAL-05 | a run with an unverified finding and LLM call stats | the run is scored | verified-quote rate = verified/reported, valid-output rate = the run's rate |
| AC-EVAL-06 | a rule-tier expected entry and a rule-check finding | scored by default / with `include_rules` | they are ignored by default and counted with `include_rules` |
| AC-EVAL-07 | score weights in the config | a run is scored | eval score = 100 × Σ weight × metric, rounded to 1 decimal |
| AC-EVAL-08 | two runs of the same model | they are scored together | metrics are averaged, stability is the share found in every run (None for one run), missed/unexpected come from the last run |
| AC-EVAL-09 | a provider and a benchmark | `evaluate` is called with repeat N | N reviews run (LLM checks only unless `include_rules`), each run and the result are saved, progress messages name the repeat, cancelling raises `ReviewCancelled` and saves no result |
| AC-EVAL-10 | several results for the same and different models, benchmarks and key versions | `leaderboard` is called | only the latest per (model, benchmark, key version) remains, sorted by eval score descending |
| AC-EVAL-11 | an `EvalStore` | results are saved and loaded | files go to `$UMR_EVALS_DIR` (default `~/.user-manual-reviewer/evals`), load back equal, oldest first, broken files skipped |
| AC-EVAL-12 | a reported finding with line numbers but no quotes | it is scored | it matches the expected finding whose quotes were located on those lines, and not when lines differ |
| AC-EVAL-13 | `config/eval.yaml` | `benchmarks()` is called | it lists the configured benchmarks; an unknown benchmark raises `KeyError` |
| AC-EVAL-14 | `samples/shopflow/expected-findings.yaml` and the sample journey | the key is checked | it loads, has 68 unique ids, every entry has a location and every quote is found by `locate_quote` |

## Examples
Expected `C2` (contradiction, major) at `order-capturing/02-creating-an-order.md` "An order can be cancelled only while it has the status Submitted." (line 57) and `delivery/dispatch.html` "Orders can be cancelled at any time until they reach the status Shipped" (line 35). A model reporting an *inconsistency* (accepted), severity *critical*, at those two quotes is matched, category-correct and gets 0.5 severity credit.

Smoke check on 2026-10-10: the deterministic rule checks alone, scored with `include_rules=True`, match all 23 rule-tier entries (plus 5 LLM-tier ones).

## Out of scope
- Running real LLMs in the default test suite (opt-in `eval` marker; not part of this feature's tests).
- Confirming unexpected findings into the key from the GUI (manual edit of the YAML for now).
- LLM-as-judge for unexpected findings.
- CLI (`umr eval`) and the GUI views; they call this API.

## Open questions
- R1 (two broken links to `payment-methods.md`) and R6 (two missing images) are one key entry each, but rule checks report one finding per link/image, so with `include_rules` the second finding counts as unexpected. Split them in key version 2?
- The real rule checks report UI labels in `05-bulk-import.md` and `legacy-sms.md` that are not in `ui-strings.json` and not in the key; the owner may confirm them into the key.
