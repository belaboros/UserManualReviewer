# Tests for DUP: Duplicate sections

Spec: [SPECIFICATIONS/DUP-duplicate-sections.md](../SPECIFICATIONS/DUP-duplicate-sections.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_duplicates.py`; manuals built in `tmp_path`.

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_DUP_01_registered_as_manual_scope_rule_check` | AC-DUP-01 | unit | registry | rule, manual, duplicate |
| `test_AC_DUP_02_identical_sections_on_different_pages` | AC-DUP-02 | unit | same 30-word body under 'Editing orders' and 'Changing an order' | one minor 'Duplicate sections' finding, 2 locations at heading lines |
| `test_AC_DUP_03_near_duplicate_across_manuals_and_formats` | AC-DUP-03 | unit | Markdown manual vs. lightly edited HTML manual | one 'Near-duplicate', similarity and 'two different manuals' in explanation |
| `test_AC_DUP_04_different_sections_not_reported` | AC-DUP-04 | unit | two unrelated sections | no finding |
| `test_AC_DUP_05_short_sections_ignored` | AC-DUP-05 | unit | two identical 6-word sections | no finding |
| `test_AC_DUP_06_duplicated_parent_reported_once_not_per_child` | AC-DUP-06 | unit | same page with two subsections in two manuals | one finding at the h1 headings |
| `test_AC_DUP_06_parent_and_child_not_reported_as_duplicates` | AC-DUP-06 | unit | 'Parent' whose only content is 'Child' | no finding |
| `test_AC_DUP_07_same_page_duplicates_point_to_both_headings` | AC-DUP-07 | unit | two '## Same' sections on one page | one finding, lines 3 and 7, 'on the same page' |
| `test_AC_DUP_08_sample_review_duplicate_findings_verified` | AC-DUP-08 | integration | ShopFlow sample, rule review | findings, all verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
