# User Manual Reviewer

A desktop application that reviews a set of related user manuals (Markdown or HTML) with rule-based checks and LLMs, and shows the results visually.

It finds duplicate sections, broken links, inconsistencies within a manual, contradictions between manuals, gaps in the end-to-end user journey, terminology drift, UI label mismatches and more. Every finding quotes the exact passage. A quality score (100% = no problems) is computed for the whole set, each manual and each page, two LLMs can be compared side by side, and a new LLM can be evaluated against sample manuals with a known answer key to see how well it does this job.

> **Status:** first working version, ready for owner testing. ADRs stay *Proposed* until the owner has tested the app.

## Quickstart

Requires [uv](https://docs.astral.sh/uv/) (`brew install uv` on macOS). Python 3.12 is installed by uv automatically.

```bash
uv sync                                   # install dependencies
uv run umr gui                            # start the desktop app
```

Rule checks work without any API key. To use LLMs:

```bash
cp config/llm-providers.example.yaml config/llm-providers.yaml   # edit models as you like
export ANTHROPIC_API_KEY=...              # or OPENAI_API_KEY, GEMINI_API_KEY; or put them in .env
uv run umr providers                      # shows which models have a key
```

Local models: start Ollama or LM Studio, and the `local-ollama` / `local-lmstudio` entries work without a key.

### Command line

```bash
uv run umr review samples/shopflow                       # rule checks only
uv run umr review samples/shopflow --model claude-sonnet # rule + LLM checks
uv run umr compare samples/shopflow claude-sonnet gpt    # two models side by side
uv run umr eval --model local-ollama                     # how good is this model for the task?
uv run umr eval --leaderboard                            # all evaluated models, ranked
uv run umr checks                                        # list checks
```

Runs are saved in `~/.user-manual-reviewer/runs/`, evaluations in `~/.user-manual-reviewer/evals/`.

### Development

```bash
uv run pytest                              # all tests (no network, no keys)
uv run ruff check src tests scripts && uv run mypy
uv run python scripts/traceability.py      # regenerates TEST_SPECS/traceability.md
```

## Understand the application in two steps

1. **[Architecture design](docs/architecture/README.md)**: what the app does, its building blocks, data model, runtime flows, scoring and GUI.
2. **[Architecture decision records](docs/adr/README.md)**: why it is built this way, with the alternatives that were rejected.

Then, for detail: [feature list](SPECIFICATIONS/FEATURES.md) and the specs in `SPECIFICATIONS/`.

## Repository layout

```
docs/architecture/   architecture design (start here)
docs/adr/            architecture decision records
SPECIFICATIONS/      feature specs with acceptance criteria (source of truth)
TEST_SPECS/          test specifications and traceability
src/umr/             application code (one package per building block)
tests/               automated tests, named after acceptance criteria
scripts/             traceability report generator
config/              example LLM provider config, scoring parameters
samples/shopflow/    sample manuals with planted mistakes, and the answer key
SDD_PROCESS.md       how we work: spec → tests → code → verify
DEVELOPMENT_LOG.md   progress log
```

## Sample manuals

`samples/shopflow/` holds three manuals of a fictional e-commerce system (order capturing, delivery, notifications) that together form one user journey. They contain deliberately planted mistakes, listed in [samples/shopflow/ANSWER_KEY.md](samples/shopflow/ANSWER_KEY.md), with a machine-readable version (`expected-findings.yaml`, added with the EVAL spec) that `umr eval` uses to score LLMs (see ADR-0013).

## Roadmap

1. Architecture design and ADRs ✓
2. Feature specifications and test specifications ✓
3. Implementation: ingest, rule checks, LLM providers, LLM checks, scoring ✓
4. GUI: dashboard, findings, comparison, LLM evaluation and leaderboard ✓
5. Owner testing, then ADRs approved ← *current*

## License

See [LICENSE](LICENSE).
