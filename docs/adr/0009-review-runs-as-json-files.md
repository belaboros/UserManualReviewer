# ADR-0009: Store review runs as JSON files

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Runs must be reopened later, compared side by side and occasionally shared. The data volume is small (hundreds of findings per run).

## Decision
Each run is one JSON file in `~/.user-manual-reviewer/runs/`, named `<timestamp>-<journey>-<model>.json`. It contains the run configuration, check and prompt versions, model, scoring parameters, findings, scores, usage and errors. The schema is versioned (`schema_version`) and defined by the Pydantic models in `domain`.

## Consequences
- Runs are human-readable, diffable and easy to attach to a bug report.
- No database migrations; listing runs means reading a folder.
- Queries across many runs are slower; acceptable at this scale.

## Alternatives considered
- **SQLite** – better for querying many runs, but opaque to users and needs migrations; can be added later as an index.
