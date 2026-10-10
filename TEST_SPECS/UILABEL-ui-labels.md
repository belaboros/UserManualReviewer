# Tests for UILABEL: UI labels

Spec: [SPECIFICATIONS/UILABEL-ui-labels.md](../SPECIFICATIONS/UILABEL-ui-labels.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_ui_labels.py`; manuals and a small `ui-strings.json` built in `tmp_path`.

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_UILABEL_01_registered_and_only_applies_with_reference` | AC-UILABEL-01 | unit | registry; journey without `ui_strings` | rule, page, ui-label; not applicable, no findings |
| `test_AC_UILABEL_02_reference_labels_are_all_string_leaves` | AC-UILABEL-02 | unit | nested JSON with arrays and `_` keys | exact label set |
| `test_AC_UILABEL_03_unknown_label_after_action_verb_reported` | AC-UILABEL-03 | unit | 'Click **Submit Order**', 'Click **Save**' | one major finding, quote `**Submit Order**`, 'Place Order' suggested |
| `test_AC_UILABEL_03_verbs_recognised` | AC-UILABEL-03 | unit | select, press, tap the … button, choose, open, go to, double-click | one finding per line |
| `test_AC_UILABEL_04_html_strong_and_b` | AC-UILABEL-04 | unit | `<strong>Load</strong>`, `<strong>Shipped</strong>` without verb, `<b>Mark as delivered</b>` | one finding for Load, 'Did you mean Load parcel' |
| `test_AC_UILABEL_05_bold_without_action_verb_ignored` | AC-UILABEL-05 | unit | bold role/field names, verb too far away | no finding |
| `test_AC_UILABEL_06_menu_paths_compared_as_whole_and_by_segment` | AC-UILABEL-06 | unit | known path in 3 spellings, unknown path, 'Preferences › Language' | findings at lines 4 and 7; unknown entries named; closest path suggested |
| `test_AC_UILABEL_07_case_only_mismatch_is_minor_with_suggestion` | AC-UILABEL-07 | unit | 'Click **Sign In**' | minor, 'Did you mean Sign in' |
| `test_AC_UILABEL_08_several_labels_on_one_line_give_one_finding` | AC-UILABEL-08 | unit | 'Click **Foo** or **Bar**, then click **Save**' | one finding naming Foo and Bar |
| `test_AC_UILABEL_09_code_blocks_ignored` | AC-UILABEL-09 | unit | `click **Nope**` in a fence | no finding |
| `test_AC_UILABEL_10_sample_review_ui_label_findings_verified` | AC-UILABEL-10 | integration | ShopFlow sample, rule review | findings, all verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
