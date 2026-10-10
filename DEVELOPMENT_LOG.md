# Development log

## 2026-10-10 · Step 1: architecture and ADRs

- Created the repository structure for specification-driven development.
- Wrote the [architecture design](docs/architecture/README.md) and ADRs 0001–0013 (status: Proposed, awaiting owner review).
- Added the ShopFlow sample manuals with planted mistakes and their answer key.
- Added the LLM evaluation feature (ADR-0013, architecture section 8, `config/eval.yaml`).
- Next: owner review of the architecture and ADRs, then step 2 (feature specifications).

## 2026-10-10 · Steps 2–4: specs, implementation, GUI

- The owner reviewed the design ("looks good"), kept the ADRs Proposed, and asked to build the app first and approve the ADRs after testing. Specs were therefore approved by that go-ahead and written together with the code.
- 19 feature specs, 190 acceptance criteria, all covered by tests (`TEST_SPECS/traceability.md`); 260 tests pass with no network or API keys; ruff and mypy clean.
- Core: ingest with source line mapping, quote verification, scoring, review runs, CLI (`umr review | compare | eval | checks | providers | gui`).
- 8 rule checks (links, images, orphans, duplicates, numbering, code, ui-labels, versions) and 5 LLM checks (contradictions, consistency, procedures, journey, terminology).
- LLM layer: OpenAI-compatible adapter (json_schema / json_object / prompt modes) and native Claude adapter (prompt caching, structured output), config file with keys from environment variables, validated output with one retry.
- Comparison of two models and LLM evaluation against `samples/shopflow/expected-findings.yaml` (68 entries, all quotes verified), with eval score and leaderboard.
- PySide6 GUI: setup, dashboard (score rings, severity bars, heatmap), findings table with filters and detail, compare, evaluate, leaderboard.
- Deviation recorded in ADR-0002 (still Proposed): passages use `QTextBrowser` instead of `QWebEngineView`.
- Not yet verified against live LLM APIs (no keys in the build environment). Rule-only review of the samples: 33 findings, rule recall 0.40 of all 68 planted problems (the rest need an LLM), set score 2.1% because the samples are deliberately dense with mistakes.
- Open questions: split answer-key entries R1/R6 per occurrence; confirm extra UI-label findings in `05-bulk-import.md` and `legacy-sms.md` into the key; tune scoring `k` after testing real manuals.
- Renamed the test-specification folder `TESTS/` to `TEST_SPECS/`: on macOS's case-insensitive file system `TESTS/` and `tests/` are the same folder.

## 2026-10-10 · LLM call log

- Owner report: local LLM calls fail. Added a call log (AC-LLM-22…27): every request (URL, model, full body) and its response or error (HTTP status and the server's response body) goes to `~/.user-manual-reviewer/logs/llm-calls-YYYY-MM-DD.jsonl`; keys are never logged.
- `umr -v` prints a summary line per call; the GUI run log shows the same lines; `umr providers --test NAME` sends one tiny request.
