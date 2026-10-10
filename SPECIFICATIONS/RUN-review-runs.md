# RUN: Review runs and command line

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.)
- **Related ADRs:** ADR-0006, ADR-0009
- **Depends on:** INGEST, FIND, SCORE

## Purpose
Run selected checks on a journey, report progress, survive failing checks, and save a self-contained run file; offer the same through a command line.

## Behaviour
- Check selection: `all`, `rules`, `llm`, or a list of ids. Without a model, LLM checks are skipped.
- Rule checks run first in order; LLM checks run concurrently up to the provider's `max_concurrency`.
- Progress events: `started`, `check_started`, `check_finished` (with the result), `finished`. A set cancel event raises `ReviewCancelled`.
- A check that raises is recorded in `errors`; the run continues.
- Findings get ids `F001…` in check order. Usage and LLM call stats are summed.
- Runs are saved as JSON (`~/.user-manual-reviewer/runs`, or `UMR_RUNS_DIR`) and load back identically.
- CLI: `umr review <journey> [--model M] [--checks …] [--json]`, `umr compare <journey> A B`, `umr eval --model M`, `umr eval --leaderboard`, `umr checks`, `umr providers`, `umr gui`.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-RUN-01 | checks "rules" and no model | a review runs | only rule-tier checks run |
| AC-RUN-02 | "all" and no model | a review runs | LLM checks are skipped, not failed |
| AC-RUN-03 | a check that raises an exception | a review runs | the error is recorded and the other checks' findings are kept |
| AC-RUN-04 | a review | it runs | progress reports started, every check finished, and finished, with done/total counts |
| AC-RUN-05 | a set cancel event | a review runs | `ReviewCancelled` is raised |
| AC-RUN-06 | a finished run | it is saved and loaded | the loaded run equals the saved one |
| AC-RUN-07 | an LLM check and a fake model | a review runs | the run records the model name, usage and LLM call stats |
| AC-RUN-08 | the CLI with `review <folder>` | it runs | it prints the set score and saves a run file, exit code 0 |
| AC-RUN-09 | the CLI with a missing journey | it runs | it prints an error and exits with code 2 |
