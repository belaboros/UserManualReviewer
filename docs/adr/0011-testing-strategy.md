# ADR-0011: Test with a fake LLM, recorded responses and an answer key

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Tests must be fast, free and repeatable, yet we also need to know whether real models find the planted problems.

## Decision
- **Unit tests** for `domain`, `ingest`, rule checks and `scoring`, with small fixture manuals.
- **LLM checks** are tested with `FakeProvider`, which returns recorded responses, so prompt building, parsing, validation and quote verification are tested offline.
- **GUI tests** with `pytest-qt` for the main flows only.
- **Evaluation** (opt-in, uses real models): `umr eval` scores a model against `samples/shopflow/expected-findings.yaml`, see [ADR-0013](0013-llm-evaluation-benchmark.md). Not part of the default test run.
- A unit test checks that every quote in `expected-findings.yaml` still exists in the sample manuals.
- Every test names the acceptance criterion it covers, for example `test_AC_LINK_03_broken_anchor_reported`.

## Consequences
- The default test suite needs no network and no API keys.
- Recorded responses must be refreshed when prompts change.

## Alternatives considered
- **Live LLM calls in every test run** – slow, costly, flaky.
- **No evaluation** – we would not know whether LLM checks actually work.
