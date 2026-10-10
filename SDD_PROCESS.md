# Specification-driven development process

Specifications are the source of truth. Code implements specs; tests prove it. Decision record: [ADR-0012](docs/adr/0012-specification-driven-development.md).

## Lifecycle of a feature

| Step | Output | Done when |
|---|---|---|
| 1. Specify | `SPECIFICATIONS/<ID>-<name>.md` from [the template](SPECIFICATIONS/TEMPLATE.md), status `Draft` | user stories, acceptance criteria, examples, out-of-scope listed |
| 2. Approve | status `Approved` | the owner has reviewed and approved the spec |
| 3. Specify tests | `TEST_SPECS/<ID>-<name>.md` from [the template](TEST_SPECS/TEMPLATE.md) | every acceptance criterion has at least one test case |
| 4. Write failing tests | `tests/...` | tests named after criteria, e.g. `test_AC_LINK_03_...`, fail |
| 5. Implement | `src/umr/...` | tests pass, lint and type checks pass |
| 6. Verify | spec status `Implemented`, log entry | every criterion is traced to a passing test in `TEST_SPECS/traceability.md` |

## Rules

- No code for a feature whose spec is not `Approved`.
- One acceptance criterion = one observable behaviour, written as Given / When / Then.
- Criterion ids are permanent: `AC-<FEATURE>-<NN>`. Removed criteria are struck through, not renumbered.
- A behaviour change updates the spec in the same pull request. Never change a spec to match a bug.
- A decision with long-term impact gets an ADR.
- Code comments reference spec sections only where the link is not obvious.

## Pull request checklist

- [ ] Spec approved and linked
- [ ] Every new or changed acceptance criterion has a test with its id in the name
- [ ] `uv run pytest`, `uv run ruff check`, `uv run mypy` pass
- [ ] Spec status and `DEVELOPMENT_LOG.md` updated
- [ ] ADR added or superseded if a decision changed
