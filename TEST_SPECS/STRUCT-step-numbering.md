# Tests for STRUCT: Step numbering

Spec: [SPECIFICATIONS/STRUCT-step-numbering.md](../SPECIFICATIONS/STRUCT-step-numbering.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_numbering.py`; manuals built in `tmp_path`.

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_STRUCT_01_registered_as_page_scope_rule_check` | AC-STRUCT-01 | unit | registry | rule, page, step-order |
| `test_AC_STRUCT_02_skipped_number_reported_as_major` | AC-STRUCT-02 | unit | `1. 2. 3. 5.` | major 'skips from 3 to 5', 'step 4 is missing', line 6 |
| `test_AC_STRUCT_03_repeated_number_reported` | AC-STRUCT-03 | unit | `1. 2. 3. 3.` | minor 'Step number 3 is used twice', line 6 |
| `test_AC_STRUCT_04_backwards_number_reported` | AC-STRUCT-04 | unit | `1. 2. 3. 2.` | 'goes back from 3 to 2' |
| `test_AC_STRUCT_05_correct_lists_not_reported` | AC-STRUCT-05 | unit | loose list with continuation, list starting at 4, `1. 1. 1.` | no finding |
| `test_AC_STRUCT_06_nested_lists_and_code_checked_separately` | AC-STRUCT-06 | unit | outer 1-3 with inner lists 1,2 and 1,3; numbers in a fence | one finding for the inner skip at line 8 |
| `test_AC_STRUCT_07_html_headings_not_treated_as_steps` | AC-STRUCT-07 | unit | `<h1>1. Intro</h1>`, `<h2>3. Later</h2>` | no finding |
| `test_AC_STRUCT_07_html_text_numbers_checked` | AC-STRUCT-07 | unit | `<p>1.`, `<p>2.`, `<p>4.`, an `<ol>` | one skip finding at line 5 |
| `test_AC_STRUCT_08_one_finding_per_break` | AC-STRUCT-08 | unit | `1. 2. 2. 5. 6.` | repeat at line 5, skip at line 6 |
| `test_AC_STRUCT_09_sample_review_numbering_findings_verified` | AC-STRUCT-09 | integration | ShopFlow sample, rule review | findings, all verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
