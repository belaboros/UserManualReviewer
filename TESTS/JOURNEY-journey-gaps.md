# Tests for JOURNEY: Gaps in the end-to-end journey

Spec: [SPECIFICATIONS/JOURNEY-journey-gaps.md](../SPECIFICATIONS/JOURNEY-journey-gaps.md)

In `tests/checks/llm/test_llm_checks.py` (budget splitting in `test_AC_PROMPT_08_*`).

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_JOURNEY_01_registered_journey_scope` | AC-JOURNEY-01 | unit | registry | properties |
| `test_AC_JOURNEY_02_single_location_gap_accepted` | AC-JOURNEY-02 | unit | canned findings | 2 kept |
| `test_AC_JOURNEY_03_instruction_walks_the_journey` | AC-JOURNEY-03 | unit | FakeProvider | instruction and corpus header |
