# Tests for VERSION: Stale version mentions

Spec: [SPECIFICATIONS/VERSION-stale-versions.md](../SPECIFICATIONS/VERSION-stale-versions.md)

Code under test: `src/umr/checks/rules/`. Tests: `tests/checks/rules/test_rules_versions.py`; manuals built in `tmp_path` (title 'Acme …', so the product name is 'Acme').

Every unit test runs the check through `run_check` (`tests/checks/rules/helpers.py`), which also runs quote verification and asserts that each finding is verified, keeps its line numbers, has `source="rule"`, `confidence=1.0`, a declared category, a title, an explanation and a suggested fix.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_VERSION_01_registered_and_applies_only_with_versions` | AC-VERSION-01 | unit | registry; manual without version | rule, manual, stale-version; not applicable |
| `test_AC_VERSION_02_product_version_claim_differs` | AC-VERSION-02 | unit | '… order flow in Acme 3.2.' with version 3.4 | minor, 'older version', quote 'Acme 3.2' |
| `test_AC_VERSION_03_version_and_v_patterns` | AC-VERSION-03 | unit | 'version 3.1', 'show v4.0', 'See v3.4' | findings at lines 3 and 5; 'different version' |
| `test_AC_VERSION_04_matching_versions_not_reported` | AC-VERSION-04 | unit | 'Acme 3.4', 'Acme 3.4.2', 'version 3.4.' | no finding |
| `test_AC_VERSION_05_historical_future_and_range_context_ignored` | AC-VERSION-05 | unit | removed in, planned for, 2.x, 3.2+, since, upgrade from | no finding |
| `test_AC_VERSION_06_other_products_and_code_ignored` | AC-VERSION-06 | unit | Chrome 120, Python version 3.12, fence, `/api/v1.2/` | no finding |
| `test_AC_VERSION_07_manual_without_version_not_checked` | AC-VERSION-07 | unit | two manuals, only `b` has a version | finding only in b |
| `test_AC_VERSION_08_several_mentions_on_one_line_give_one_finding` | AC-VERSION-08 | unit | 'Acme 3.1 and Acme 3.2' | one finding naming both |
| `test_AC_VERSION_09_sample_review_version_findings_verified` | AC-VERSION-09 | integration | ShopFlow sample, rule review | findings, all verified |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
