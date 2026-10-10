# Tests for GUI: Desktop application

Spec: [SPECIFICATIONS/GUI-desktop-app.md](../SPECIFICATIONS/GUI-desktop-app.md)

All tests are in `tests/gui/`, marked `@pytest.mark.gui`, and run offscreen without network or API keys:
`QT_QPA_PLATFORM=offscreen uv run pytest tests/gui -q`.

Fixtures (`tests/gui/conftest.py`, `tests/gui/gui_helpers.py`): a `MainWindow` with a temporary `QSettings` file, `RunStore` and `EvalStore`, its own `QThreadPool`, two `FakeProvider`s (`fake-a`, `fake-b`), a `StubReviewService` that resolves stub checks instead of the global registry (so the registry is not changed), and a fake `EvalService`. Stub checks: `stub-value` (rule, quotes "You can add up to 50 line items to one order."), `stub-link` (rule, line 12 of `delivery/dispatch.html`), `stub-llm` (LLM, invented quote → unverified), `stub-fail` (raises), `stub-empty` (no findings), `stub-slow` (blocks until released, for cancelling). Error dialogs are switched off (`dialogs_enabled = False`) and the last error is asserted instead.

| Test | Criterion | Kind | Input / fixture | Expected |
|---|---|---|---|---|
| `test_AC_GUI_01_window_opens_with_sidebar_and_empty_state` | AC-GUI-01 | gui | fresh window | six sidebar entries, Setup shown, "Open a journey to start" |
| `test_AC_GUI_02_open_sample_journey_lists_three_manuals` | AC-GUI-02 | gui | `samples/shopflow/journey.yaml` | 3 manuals with pages and word counts, title has journey name, path in settings |
| `test_AC_GUI_02_initial_journey_is_remembered_path` | AC-GUI-02 | gui | two windows, one settings file | second window opens the remembered journey |
| `test_AC_GUI_02_bad_journey_shows_readable_error` | AC-GUI-02 | gui | missing file | "Could not open the journey" |
| `test_AC_GUI_03_check_buttons_group_and_badge` | AC-GUI-03 | gui | 2 rule + 1 LLM stub | tier groups, `needs LLM` badge, All / Rules only / None, summary |
| `test_AC_GUI_03_selection_summary_counts_llm_checks` | AC-GUI-03 | unit | `CheckInfo` list | "2 of 3 checks selected · 1 need an LLM", skip warning without model |
| `test_AC_GUI_04_model_pickers_list_providers` | AC-GUI-04 | gui | fake catalog | "None — rule checks only"/"None — no comparison" + providers; Start becomes "Start comparison" |
| `test_AC_GUI_04_example_config_notice` | AC-GUI-04 | gui | missing `llm-providers.yaml`, real example file | notice mentions example and environment variables; providers listed |
| `test_AC_GUI_05_start_runs_in_worker_logs_and_saves` | AC-GUI-05 | gui | stub rule checks | check ran off the GUI thread, log lines with counts, progress 100, run saved, Dashboard shown |
| `test_AC_GUI_05_progress_lines` | AC-GUI-05 | unit | `ProgressEvent`s | log line text incl. errors and side label |
| `test_AC_GUI_06_cancel_stops_review` | AC-GUI-06 | gui | `stub-slow` | `task_ended("cancelled")`, log says cancelled, Start enabled, nothing saved |
| `test_AC_GUI_07_dashboard_shows_scores_charts_and_facts` | AC-GUI-07 | gui | run with fake-a | ring value and band colour, 3 cards, severity counts, heatmap cell, model/duration/tokens/cost |
| `test_AC_GUI_07_dashboard_with_real_rule_checks` | AC-GUI-07 | gui | registered rule checks on the samples | dashboard and table filled (skipped if none registered) |
| `test_AC_GUI_07_score_band_colours` | AC-GUI-07 | unit | 100, 90, 89.9, 70, 69.9, 0 | green / amber / red |
| `test_AC_GUI_08_failed_check_listed_on_dashboard` | AC-GUI-08 | gui | `stub-fail` | errors box lists the check and message; log shows ✗ line |
| `test_AC_GUI_09_findings_table_columns_and_rows` | AC-GUI-09 | gui | 3 findings | 8 columns in order, one row per finding, manual/page/source cells |
| `test_AC_GUI_09_severity_sorts_by_rank` | AC-GUI-09 | gui | 3 findings | critical, major, minor when sorted descending |
| `test_AC_GUI_10_findings_filter_by_severity_category_manual_verified_text` | AC-GUI-10 | gui | 3 findings | each filter narrows rows; no match → "No findings match the filters" |
| `test_AC_GUI_10_finding_filter_combines_with_and` | AC-GUI-10 | unit | `FindingFilter` | AND of all filters; multi-word text search |
| `test_AC_GUI_11_unverified_finding_greyed_and_marked` | AC-GUI-11 | gui | invented quote | muted foreground, italic, "unverified" |
| `test_AC_GUI_12_finding_detail_highlights_quote` | AC-GUI-12 | gui | `stub-value` finding | title, explanation, fix, quote, line numbers n−5…n+5 only, mark colour |
| `test_AC_GUI_12_detail_unverified_location_says_not_found` | AC-GUI-12 | gui | invented quote | "passage not found in the source" with the quote |
| `test_AC_GUI_12_passage_html_numbers_context_and_marks_quote` | AC-GUI-12 | unit | verified location | ±5 numbered lines, one highlighted row, quote wrapped in a mark span |
| `test_AC_GUI_12_passage_html_html_page_uses_readable_text` | AC-GUI-12 | unit | `delivery/dispatch.html` line 12 | no HTML markup in the passage |
| `test_AC_GUI_12_passage_html_missing_source` | AC-GUI-12 | unit | no journey | "source not available" with the quote |
| `test_AC_GUI_13_compare_view_groups_findings` | AC-GUI-13 | gui | hand-built `Comparison` | group titles with counts, scores, cost, duration, tokens side by side |
| `test_AC_GUI_13_clicking_a_finding_shows_detail` | AC-GUI-13 | gui | hand-built `Comparison` | detail shows A's finding and B's title; one selection across lists |
| `test_AC_GUI_13_compare_two_saved_runs` | AC-GUI-13 | gui | two saved runs | `CompareService.compare_runs` result shown; one file → error |
| `test_AC_GUI_14_eval_view_renders_result` | AC-GUI-14 | gui | hand-built `EvalResult` | score, metrics, per-category rows with bar values, missed and unexpected lists |
| `test_AC_GUI_15_leaderboard_lists_and_sorts` | AC-GUI-15 | gui | 3 saved `EvalResult`s | ranked by score; numeric sort on score and cost; all columns |
| `test_AC_GUI_15_leaderboard_empty_state` | AC-GUI-15 | gui | no results | "No evaluations yet — run one in Evaluate." |
| `test_AC_GUI_16_open_saved_run` | AC-GUI-16 | gui | run file | dashboard and table filled, journey re-loaded, listed under Recent runs |
| `test_AC_GUI_16_open_broken_run_shows_error` | AC-GUI-16 | gui | invalid JSON | "Could not open the run" |
| `test_AC_GUI_17_missing_api_key_shows_error_dialog` | AC-GUI-17 | gui | factory raising `LlmError` | "Model error" naming the env var and `api_key_env`; no review started |
| `test_AC_GUI_17_no_journey_and_no_checks_errors` | AC-GUI-17 | gui | no journey; no checks | readable errors |
| `test_AC_GUI_17_friendly_error_messages` | AC-GUI-17 | unit | `LlmError`, `IngestError`, `FileNotFoundError` | dialog titles and hints |
| `test_AC_GUI_18_keyboard_shortcuts` | AC-GUI-18 | gui | patched file dialog, `stub-slow` | Ctrl+O opens, Ctrl+R starts, Esc cancels |
| `test_AC_GUI_19_zero_findings_empty_state` | AC-GUI-19 | gui | `stub-empty` | "No findings — 100%" on dashboard and in Findings; ring 100 |
| `test_AC_GUI_20_model_b_runs_comparison` | AC-GUI-20 | gui | fake-a vs fake-b | both runs saved, Compare view shown, log labelled A/B, progress 100 |
| `test_AC_GUI_21_evaluate_runs_in_worker_and_saves` | AC-GUI-21 | gui | fake `EvalService` | options passed through, ran off the GUI thread, result shown and saved, leaderboard refreshed |

Kinds: `unit`, `integration`, `gui`, `eval` (opt-in, uses real LLMs).
