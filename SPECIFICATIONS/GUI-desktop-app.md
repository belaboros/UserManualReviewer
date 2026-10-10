# GUI: Desktop application

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.)
- **Related ADRs:** ADR-0002, ADR-0007, ADR-0008, ADR-0010, ADR-0013
- **Depends on:** INGEST, FIND, SCORE, RUN, LLM, COMPARE, EVAL

## Purpose
Give documentation authors a desktop window in which they open a journey, pick checks and models, run a review without freezing the window, and then read the result visually: scores, charts, a filterable findings table, the quoted source passages, a side-by-side comparison of two models, an LLM evaluation and a leaderboard.

## User stories
- As a documentation author, I want to open my `journey.yaml` and see the manuals and pages it contains, so that I know what will be reviewed.
- As an author, I want to choose checks and a model and start a review that I can cancel, so that I stay in control of time and cost.
- As an author, I want a dashboard with the quality score and where the problems are, so that I know where to start.
- As an author, I want to filter findings and see each quoted passage highlighted in context, so that I can verify and fix it quickly.
- As an owner trying a new model, I want to compare two models and evaluate a model against the benchmark, so that I can pick the best model for the price.

## Behaviour

### Main window
- Entry point `umr.gui.app:main()`; also `python -m umr.gui`. The CLI's `umr gui` calls `main()`.
- Left sidebar with the views **Setup, Dashboard, Findings, Compare, Evaluate, Leaderboard**; the right side shows the selected view.
- Window title: `User Manual Reviewer — <journey name>` once a journey or run is open.
- Menu **File**: Open journey… (Ctrl+O), Open journey folder…, Open run… (Ctrl+Shift+O), Recent runs ▸, Compare two runs…, Quit (Ctrl+Q). Menu **Review**: Start (Ctrl+R), Cancel (Esc).
- Status bar messages for loading, progress, saving and errors.
- Errors are shown in readable dialogs (title + one-paragraph message + hint). A missing API key (`LlmError`) names the environment variable to set.
- Colours: score bands and severities use mid-saturation colours legible on light and dark palettes; text always uses the palette's text colour; every coloured element also shows its value as text.

### Setup
- Open a journey from a `journey.yaml` file or a folder (with `journey.yaml`, or a single manual folder). The last path is remembered in `QSettings`; on first start `samples/shopflow/journey.yaml` (relative to the working directory) is opened if it exists.
- Manuals tree: one row per manual (title, id, version, total words) with its pages (path, format, words).
- Checks tree grouped by tier (**Rule checks**, **LLM checks**), each with a tick box, title and description tooltip; LLM checks carry a `needs LLM` badge. Buttons **All**, **Rules only**, **None**. A summary label says how many checks are selected and how many need an LLM; when no model A is chosen it warns that LLM checks will be skipped.
- Model A: `None — rule checks only` plus every configured provider. Model B: `None — no comparison` plus every provider; choosing B makes Start run a comparison.
- Providers come from `config/llm-providers.yaml`; if that file is missing, `config/llm-providers.example.yaml` is used and a notice says so and that keys come from environment variables. If the provider layer is not available, only rule checks can be run and a notice says so.
- **Start** runs the review in a `QThreadPool` worker; progress events are marshalled to the GUI thread with Qt signals. **Cancel** sets the cancel event. A progress bar shows done/total; a log lists check started/finished with finding counts, errors and the final result.
- After a run the run file is saved automatically with `RunStore().save`, the dashboard is shown, and the findings table is filled.

### Dashboard
- Empty state: "Run a review or open a saved run to see the dashboard."
- Set score as a large ring gauge; colour band ≥ 90 green, ≥ 70 amber, else red; the number is always written in the middle.
- One score card per manual (small ring, title, finding count).
- Bar chart of findings by severity (verified and unverified shown separately).
- Heatmap of pages × categories: cell = number of verified findings with a location on that page; colour intensity grows with the count; the count is written in the cell.
- Run facts: journey, model, checks, started, duration, tokens (in/out/cached), cost, and the list of failed checks with their messages.
- With zero findings: "No findings — 100%".

### Findings
- `QTableView` over a `QSortFilterProxyModel`; columns: Id, Severity, Category, Title, Manual(s), Page(s), Source, Verified.
- Filters: severity, category, manual, verified only, free text (title, explanation, suggested fix, quotes, pages, id). Filters combine with AND.
- Severity sorts by rank (critical first when descending), not alphabetically.
- Unverified findings are greyed and italic and show `unverified` in the Verified column.
- Empty states: "Open a journey to start" (no run), "No findings — 100%" (run without findings), "No findings match the filters".

### Finding detail
- Panel below the table in a splitter, so two passages fit side by side at full width (also in the Compare view): title, severity, category, check, source, explanation, suggested fix, then one source passage per location side by side (two per row), each with ±5 lines of context, line numbers, the located lines highlighted and the quoted text marked.
- HTML pages show their readable text per source line; Markdown pages show the source line.
- When a location has no line numbers or the page cannot be found, the quote is shown with "passage not found in the source".
- **Deviation from ADR-0002 / architecture section 12:** passages and comparisons are rendered in a `QTextBrowser`, not `QWebEngineView`, because it is lighter, starts instantly and works offscreen in tests. To be recorded by the lead in the ADR.

### Compare
- Filled after a review with model B, or via File → Compare two runs….
- Header table with both runs side by side: model, set score, findings, verified findings, tokens, cost, duration.
- Three lists: **Found by both (n)**, **Only <A> (n)**, **Only <B> (n)**; clicking an item shows its detail below.

### Evaluate
- Pick provider, benchmark (from `EvalService().benchmarks()`), repeat count (1–10), include-rules tick box; **Run** and **Cancel**; progress bar.
- Result: eval score in large type, metrics (recall, precision, F1, category accuracy, severity accuracy, verified-quote rate, valid-output rate, stability), cost, tokens, duration; per-category table (expected, found, reported, recall, precision, F1) where the three rates are drawn as bars with the number; lists of missed expected findings and unexpected findings.
- The result is saved with `EvalStore().save()` and the leaderboard refreshes.

### Leaderboard
- Table of `leaderboard(EvalStore().load_all())`: Rank, Model, Benchmark, Key version, Eval score, Recall, Precision, F1, Verified quotes, Valid output, Cost, Duration, Date. Sortable on every column, numeric columns sort numerically.
- Empty state: "No evaluations yet — run one in Evaluate."

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-GUI-01 | a fresh start | the main window opens | it shows the sidebar with Setup, Dashboard, Findings, Compare, Evaluate, Leaderboard and the empty state "Open a journey to start" |
| AC-GUI-02 | the Setup view | `samples/shopflow/journey.yaml` is opened | the manuals tree lists 3 manuals with their pages and word counts, the window title contains the journey name, and the path is remembered in settings |
| AC-GUI-03 | a check list with rule and LLM checks | the user clicks All, Rules only and None | the tick boxes follow, checks are grouped by tier, LLM checks show a `needs LLM` badge and the summary counts them |
| AC-GUI-04 | a provider configuration | the Setup view opens | model A lists "None — rule checks only" plus the providers and model B lists "None — no comparison" plus the providers; a notice appears when the example config is used |
| AC-GUI-05 | a loaded journey and rule checks | Start is clicked | the review runs in a worker thread, the log shows started/finished lines with finding counts, the progress bar reaches 100 %, and the run is saved |
| AC-GUI-06 | a running review | Cancel is clicked | the review stops, the log says it was cancelled and Start is enabled again |
| AC-GUI-07 | a finished run | the dashboard is shown | it shows the set score with its number and band colour, one card per manual, severity counts, a pages × categories heatmap and the run's model, duration, tokens and cost |
| AC-GUI-08 | a run where a check failed | the dashboard is shown | the failed check and its message are listed |
| AC-GUI-09 | a run with findings | the Findings view is shown | the table has the columns Id, Severity, Category, Title, Manual(s), Page(s), Source, Verified with one row per finding |
| AC-GUI-10 | the findings table | a severity, category, manual, verified-only or text filter is set | only matching rows remain |
| AC-GUI-11 | an unverified finding | it is shown in the table | it is greyed and marked `unverified` |
| AC-GUI-12 | a selected finding | the detail panel shows it | it shows title, explanation and suggested fix, and every location's passage with line numbers, ±5 lines of context and the quoted line highlighted |
| AC-GUI-13 | a comparison of two runs | the Compare view shows it | it lists Found by both, Only A and Only B with counts, both set scores, tokens, cost and duration; clicking an item shows its detail |
| AC-GUI-14 | an evaluation result | the Evaluate view shows it | the eval score, the metrics, a per-category table and the missed and unexpected findings are shown |
| AC-GUI-15 | several evaluation results | the Leaderboard shows them | they appear with all columns and sort numerically by any column |
| AC-GUI-16 | a saved run file | File → Open run… loads it | the dashboard and findings show that run and it appears under Recent runs |
| AC-GUI-17 | a model whose API key is missing | Start is clicked | a readable error dialog names the problem and no review starts |
| AC-GUI-18 | the main window | Ctrl+O, Ctrl+R and Esc are pressed | they open a journey, start a review and cancel it |
| AC-GUI-19 | a run with zero findings | the dashboard and findings are shown | they say "No findings — 100%" |
| AC-GUI-20 | model B chosen in Setup | Start is clicked | both models run, both runs are saved and the Compare view opens with the comparison |
| AC-GUI-21 | an Evaluate view with a provider and benchmark | Run is clicked | the evaluation runs in a worker and its result is shown and saved |

## Examples
- Opening `samples/shopflow/journey.yaml` shows *ShopFlow order to delivery* with `order-capturing` (6 pages, 810 words), `delivery` (4 pages, 549 words) and `notification` (4 pages, 379 words).
- A rule-only review of the samples (8 rule checks) shows 33 verified findings (23 major, 10 minor), the set score ring in red with its number written in the middle, three manual cards, a heatmap of 14 pages × 9 categories, and the run file path in the status bar.

## Out of scope
- Editing manuals or fixing findings from the GUI.
- Confirming unexpected evaluation findings into the answer key (CLI / file edit for now).
- Packaging the app (separate ADR).
- Live streaming of individual findings into the table while a run is in progress (the table fills when the run finishes; the log shows counts live).

## Open questions
- Should the heatmap also count unverified findings in a separate shade?
- Should comparison and passages move to `QWebEngineView` later for richer layout (see deviation above)?
