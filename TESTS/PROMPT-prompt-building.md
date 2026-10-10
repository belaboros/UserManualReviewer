# Tests for PROMPT: Prompt building, response mapping, context budget and caching layout

Spec: [SPECIFICATIONS/PROMPT-prompt-building.md](../SPECIFICATIONS/PROMPT-prompt-building.md)

All in `tests/checks/llm/test_llm_prompting.py`, fixture journeys from `tests/checks/llm/conftest.py`.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_PROMPT_01_corpus_is_deterministic_with_page_headers` | AC-PROMPT-01 | unit | 2-manual journey | stable text, headers, order |
| `test_AC_PROMPT_02_body_is_readable_text_with_empty_runs_collapsed` | AC-PROMPT-02 | unit | Markdown with bold, links, blank lines | plain text, step numbers |
| `test_AC_PROMPT_03_reference_files_included` | AC-PROMPT-03 | unit | journey with `ui.json` | reference block first |
| `test_AC_PROMPT_03_subset_rendering` | AC-PROMPT-03 | unit | one manual / one page | only those |
| `test_AC_PROMPT_04_corpus_first_identical_across_journey_checks` | AC-PROMPT-04 | unit | 3 journey checks, FakeProvider | same prefix and system |
| `test_AC_PROMPT_04_system_prompt_requires_verbatim_quotes` | AC-PROMPT-04 | unit | `SYSTEM_PROMPT` | quote rules present |
| `test_AC_PROMPT_05_json_mapped_to_findings` | AC-PROMPT-05 | unit | response with 2 locations | domain finding |
| `test_AC_PROMPT_05_page_id_variants` | AC-PROMPT-05 | unit | decorated page ids | split correctly |
| `test_AC_PROMPT_06_unknown_category_maps_to_primary_and_severity_synonyms` | AC-PROMPT-06 | unit | odd values | normalised |
| `test_AC_PROMPT_07_findings_without_location_dropped` | AC-PROMPT-07 | unit | one finding without locations | dropped |
| `test_AC_PROMPT_08_journey_check_over_budget_runs_per_manual_pair` | AC-PROMPT-08 | unit | 3 manuals, small context | 3 pair calls, merged |
| `test_AC_PROMPT_09_manual_too_big_runs_per_page_group` | AC-PROMPT-09 | unit | tiny context | one call per page |
| `test_AC_PROMPT_09_journey_single_manual_over_budget_uses_page_groups` | AC-PROMPT-09 | unit | 1-manual journey, tiny context | 2 calls |
| `test_AC_PROMPT_10_invalid_json_error_recorded_by_review_service` | AC-PROMPT-10 | integration | ReviewService, FakeProvider | error row, stats, usage |
| `test_AC_PROMPT_10_findings_verified_through_review_service` | AC-PROMPT-10 | integration | ReviewService | verified finding with line |
| `test_AC_PROMPT_11_response_schema_shared_by_all_checks` | AC-PROMPT-11 | unit | all 5 checks | one schema |
| `test_AC_PROMPT_12_usage_and_stats_accumulate_in_context` | AC-PROMPT-12 | unit | consistency, 2 manuals | usage and stats 2 calls |
| `test_AC_PROMPT_12_check_without_provider_raises` | AC-PROMPT-12 | unit | no provider | `LlmError` |
