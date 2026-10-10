# Tests for EVAL: LLM evaluation against an answer key

Spec: [SPECIFICATIONS/EVAL-llm-evaluation.md](../SPECIFICATIONS/EVAL-llm-evaluation.md) · Code: `tests/app/test_evaluation.py`, `tests/app/test_expected_findings.py`

Most tests use a five-entry mini key (C2, G4, X28, X19 as `llm`, R2 as `rule`) over the real ShopFlow journey, hand-built `ReviewRun`s, and a test-only LLM check driven by `FakeProvider`.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_EVAL_01_answer_key_loads_with_defaults` | AC-EVAL-01 | unit | mini key file | fields, tier default `llm` |
| `test_AC_EVAL_01_answer_key_rejects_unknown_category` | AC-EVAL-01 | unit | category "nonsense" | `ValidationError` |
| `test_AC_EVAL_02_matching_ignores_category_and_category_accuracy_uses_accepted` | AC-EVAL-02 | unit | C2 as inconsistency, G4 as terminology | both matched, category accuracy 0.5 |
| `test_AC_EVAL_02_exact_category_wins_ties` | AC-EVAL-02 | unit | two key entries on one line | ui-label finding matches ui-label entry |
| `test_AC_EVAL_03_recall_precision_f1_overall_and_per_category` | AC-EVAL-03 | unit | C2, G4 + one unexpected | R 0.5, P 2/3, per-category rows, missed/unexpected |
| `test_AC_EVAL_03_nothing_reported_scores_zero` | AC-EVAL-03 | unit | empty run | all rates 0 |
| `test_AC_EVAL_04_severity_accuracy_exact_and_one_level_off` | AC-EVAL-04 | unit | exact, ±1, ±2 levels | 0.5 |
| `test_AC_EVAL_05_verified_quote_rate_and_valid_output_rate` | AC-EVAL-05 | unit | 1 of 3 unverified, 3 of 4 calls valid | 2/3 and 0.75 |
| `test_AC_EVAL_06_rule_tier_excluded_by_default_included_on_request` | AC-EVAL-06 | unit | rule finding on R2 | ignored / matched with `include_rules` |
| `test_AC_EVAL_07_eval_score_uses_configured_weights` | AC-EVAL-07 | unit | default and f1-only weights | weighted sum ×100, 1 decimal |
| `test_AC_EVAL_08_repeats_are_averaged_with_stability` | AC-EVAL-08 | unit | two runs | averages, stability 0.25, last run's missed |
| `test_AC_EVAL_09_evaluate_runs_review_and_saves_runs_and_result` | AC-EVAL-09 | integration | `FakeProvider` responder, repeat 2 | metrics, 2 run files, 1 eval file, "Run 2/2", LLM checks only |
| `test_AC_EVAL_09_evaluate_with_rules_requests_all_checks` | AC-EVAL-09 | integration | `include_rules=True` | all checks requested |
| `test_AC_EVAL_09_evaluate_can_be_cancelled` | AC-EVAL-09 | integration | responder sets cancel | `ReviewCancelled`, nothing saved |
| `test_AC_EVAL_10_leaderboard_latest_per_model_sorted_by_score` | AC-EVAL-10 | unit | five results | latest per key, sorted |
| `test_AC_EVAL_11_eval_store_round_trip_and_default_dir` | AC-EVAL-11 | unit | `UMR_EVALS_DIR`, a broken file | equal after load, oldest first |
| `test_AC_EVAL_12_expected_quotes_are_located_to_lines` | AC-EVAL-12 | unit | finding with lines only | matches X28; wrong lines do not |
| `test_AC_EVAL_13_benchmarks_from_config` | AC-EVAL-13 | unit | mini config, real `config/eval.yaml` | `["mini"]`, `KeyError`, `["shopflow"]` with 68 entries |
| `test_AC_EVAL_14_key_loads_with_unique_ids` | AC-EVAL-14 | unit | `samples/shopflow/expected-findings.yaml` | version 1, 68 unique ids |
| `test_AC_EVAL_14_every_entry_has_a_location` | AC-EVAL-14 | unit | same | every entry located, category not repeated in accept list |
| `test_AC_EVAL_14_every_quote_found_in_sample_manuals` | AC-EVAL-14 | unit | key + sample journey | every quote found by `locate_quote` |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
