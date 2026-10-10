# Tests for CONSIST: Inconsistencies within one manual, and step order logic

Spec: [SPECIFICATIONS/CONSIST-consistency.md](../SPECIFICATIONS/CONSIST-consistency.md)

In `tests/checks/llm/test_llm_checks.py`.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_CONSIST_01_registered_manual_scope` | AC-CONSIST-01 | unit | registry | properties |
| `test_AC_CONSIST_02_runs_once_per_manual` | AC-CONSIST-02 | unit | 2 manuals, FakeProvider | 2 calls, per-manual corpus |
| `test_AC_CONSIST_03_instruction_covers_inconsistency_kinds` | AC-CONSIST-03 | unit | instruction text | topics and categories |
| `test_AC_CONSIST_04_findings_mapped_per_manual` | AC-CONSIST-04 | unit | answer for `orders` only | one ui-label finding |
| `test_AC_CONSIST_05_procedures_step_order_check` | AC-CONSIST-05 | unit | `procedures` | step-order findings, instruction |
| `test_AC_CONSIST_06_manual_checks_share_the_cached_corpus` | AC-CONSIST-06 | unit | both checks | same prefixes |
