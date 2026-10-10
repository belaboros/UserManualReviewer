# Tests for TERM: Terminology drift and undefined terms

Spec: [SPECIFICATIONS/TERM-terminology.md](../SPECIFICATIONS/TERM-terminology.md)

In `tests/checks/llm/test_llm_checks.py`.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_TERM_01_registered` | AC-TERM-01 | unit | registry | properties |
| `test_AC_TERM_02_applies_to_single_manual` | AC-TERM-02 | unit | 1-manual journey | applies, one call, category |
| `test_AC_TERM_03_instruction_covers_drift_and_undefined_terms` | AC-TERM-03 | unit | FakeProvider | instruction content |
