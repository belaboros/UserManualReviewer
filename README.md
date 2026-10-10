# User Manual Reviewer

A desktop application that reviews a set of related user manuals (Markdown or HTML) with rule-based checks and LLMs, and shows the results visually.

It finds duplicate sections, broken links, inconsistencies within a manual, contradictions between manuals, gaps in the end-to-end user journey, terminology drift, UI label mismatches and more. Every finding quotes the exact passage. A quality score (100% = no problems) is computed for the whole set, each manual and each page, two LLMs can be compared side by side, and a new LLM can be evaluated against sample manuals with a known answer key to see how well it does this job.

> **Status:** design phase. Architecture and ADRs are proposed; feature specifications are next. No application code yet.

## Understand the application in two steps

1. **[Architecture design](docs/architecture/README.md)**: what the app does, its building blocks, data model, runtime flows, scoring and GUI.
2. **[Architecture decision records](docs/adr/README.md)**: why it is built this way, with the alternatives that were rejected.

Then, for detail: [feature list](SPECIFICATIONS/FEATURES.md) and the specs in `SPECIFICATIONS/`.

## Repository layout

```
docs/architecture/   architecture design (start here)
docs/adr/            architecture decision records
SPECIFICATIONS/      feature specs with acceptance criteria (source of truth)
TESTS/               test specifications and traceability
src/umr/             application code (from step 3)
tests/               automated tests (from step 3)
config/              example LLM provider config, scoring parameters
samples/shopflow/    sample manuals with planted mistakes, and the answer key
SDD_PROCESS.md       how we work: spec → tests → code → verify
DEVELOPMENT_LOG.md   progress log
```

## Sample manuals

`samples/shopflow/` holds three manuals of a fictional e-commerce system (order capturing, delivery, notifications) that together form one user journey. They contain deliberately planted mistakes, listed in [samples/shopflow/ANSWER_KEY.md](samples/shopflow/ANSWER_KEY.md), with a machine-readable version (`expected-findings.yaml`, added with the EVAL spec) that `umr eval` uses to score LLMs (see ADR-0013).

## Roadmap

1. Architecture design and ADRs ← *current*
2. Feature specifications and test specifications
3. Implementation: ingest, rule checks, LLM providers, LLM checks, scoring
4. GUI: dashboard, findings, comparison, LLM evaluation and leaderboard

## License

See [LICENSE](LICENSE).
