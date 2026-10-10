# Tests for CODE: Malformed code blocks

Spec: [SPECIFICATIONS/CODE-malformed-code.md](../SPECIFICATIONS/CODE-malformed-code.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_code.py`; manuals built in `tmp_path`.

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_CODE_01_registered_as_page_scope_rule_check` | AC-CODE-01 | unit | registry | rule, page, malformed-code |
| `test_AC_CODE_02_invalid_json_reported_at_error_line` | AC-CODE-02 | unit | ```` ```json ```` with trailing comma | major, 'trailing comma', line 7 |
| `test_AC_CODE_02_valid_json_not_reported` | AC-CODE-02 | unit | valid `json` block | no finding |
| `test_AC_CODE_03_unlabelled_block_starting_with_brace_is_json` | AC-CODE-03 | unit | unlabelled `[1, 2`, `{ ... }`, plain text | one finding for the first block |
| `test_AC_CODE_04_invalid_yaml_reported` | AC-CODE-04 | unit | bad indentation in `yaml`; valid `yml` | one finding inside the yaml block |
| `test_AC_CODE_05_csv_delimiters_and_quotes` | AC-CODE-05 | unit | quoted comma, `tsv`, tab-separated `csv` with short row | one finding ('tab'), line 16 |
| `test_AC_CODE_05_csv_rows_with_wrong_column_count` | AC-CODE-05 | unit | `;` header with 4 columns, rows of 3 and 5 | one finding, 'semicolon', locations lines 6 and 7 |
| `test_AC_CODE_06_templates_and_other_languages_skipped` | AC-CODE-06 | unit | `json` with `{{ }}`, `python`, unlabelled template | no finding |
| `test_AC_CODE_07_html_code_block_checked` | AC-CODE-07 | unit | HTML `<pre><code class="language-json">` missing comma | one finding, 'missing comma', line 5 |
| `test_AC_CODE_08_sample_review_code_findings_verified` | AC-CODE-08 | integration | ShopFlow sample, rule review | findings, all verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
