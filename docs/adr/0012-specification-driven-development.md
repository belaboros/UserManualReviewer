# ADR-0012: Specification-driven development with traceable acceptance criteria

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The owner wants specification-driven development done properly: specs are the source of truth, and it must be clear which code and tests implement which requirement.

## Decision
- Each feature has a spec in `SPECIFICATIONS/<ID>-<name>.md` with a status (`Draft`, `Approved`, `Implemented`), user stories and numbered acceptance criteria (`AC-<ID>-NN`) written as Given/When/Then.
- No code is written for a feature before its spec is `Approved` by the owner.
- Each acceptance criterion has at least one test whose name contains the criterion id; `TESTS/traceability.md` is generated from test names.
- Code changes that alter behaviour update the spec in the same pull request; specs are never edited to match a bug.
- `DEVELOPMENT_LOG.md` records each feature's progress.
- The full process is in [SDD_PROCESS.md](../../SDD_PROCESS.md).

## Consequences
- Reviewers can check a pull request against the spec criteria.
- Slightly more writing before coding; reduces rework and ambiguity, especially with AI-assisted implementation.

## Alternatives considered
- **Specs in issues** – drift away from the code they describe.
- **Tests as the only spec** – hard to review for a non-programmer reader.
