# Tests for COMPARE: Side-by-side comparison of two models

Spec: [SPECIFICATIONS/COMPARE-side-by-side-comparison.md](../SPECIFICATIONS/COMPARE-side-by-side-comparison.md) · Code: `tests/app/test_compare.py`

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_COMPARE_01_same_category_overlapping_lines_found_by_both` | AC-COMPARE-01 | unit | hand-built runs, lines 57 and 56–58 | one pair, no only-A/B |
| `test_AC_COMPARE_02_quote_similarity_threshold` | AC-COMPARE-02 | unit | findings with quotes and no lines | similar quote paired, different quote not |
| `test_AC_COMPARE_03_different_page_or_lines_not_matched` | AC-COMPARE-03 | unit | other page / other lines | nothing paired |
| `test_AC_COMPARE_04_second_pass_matches_other_category_on_strong_locations` | AC-COMPARE-04 | unit | inconsistency vs contradiction, same two locations; weak one-of-two | strong paired, weak not |
| `test_AC_COMPARE_04_same_category_preferred_over_other_category` | AC-COMPARE-04 | unit | B has a duplicate and a value-conflict on the same line | value-conflict paired |
| `test_AC_COMPARE_05_contradiction_needs_two_matching_locations` | AC-COMPARE-05 | unit | 2-location findings sharing one location | not paired; 1-location finding paired |
| `test_AC_COMPARE_06_one_to_one_pairing` | AC-COMPARE-06 | unit | two A findings, one B | one pair, one only-A |
| `test_AC_COMPARE_07_run_and_compare_runs_both_models_concurrently` | AC-COMPARE-07 | integration | sample journey, two `FakeProvider`s meeting at a `threading.Barrier`, test-only LLM check | both runs finish, progress labelled A/B, own model and usage |
| `test_AC_COMPARE_08_groups_both_only_a_only_b` | AC-COMPARE-08 | integration | A reports two findings, B one; `RunStore` in tmp | groups correct, 2 run files |
| `test_AC_COMPARE_09_cancel_stops_both_reviews` | AC-COMPARE-09 | integration | responder sets the cancel event | `ReviewCancelled` |
| `test_AC_COMPARE_10_error_in_one_review_is_raised` | AC-COMPARE-10 | unit | `ReviewService` stub that raises | `RuntimeError` reaches caller |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
