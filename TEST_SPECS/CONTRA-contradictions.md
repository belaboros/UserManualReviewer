# Tests for CONTRA: Contradictions across manuals

Spec: [SPECIFICATIONS/CONTRA-contradictions.md](../SPECIFICATIONS/CONTRA-contradictions.md)

In `tests/checks/llm/test_llm_checks.py` (also covered end-to-end by `test_AC_PROMPT_10_*`).

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_CONTRA_01_registered_journey_scope` | AC-CONTRA-01 | unit | registry, 1- and 2-manual journeys | properties, applies_to |
| `test_AC_CONTRA_02_instruction_after_corpus` | AC-CONTRA-02 | unit | FakeProvider | prefix = corpus, instruction content |
| `test_AC_CONTRA_03_needs_locations_in_two_manuals` | AC-CONTRA-03 | unit | three canned findings | one kept |
| `test_AC_CONTRA_04_value_conflict_and_unknown_category` | AC-CONTRA-04 | unit | canned findings | categories, source |
