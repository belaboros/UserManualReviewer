# ADR-0001: Record architecture decisions as ADRs

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The project owner wants to understand the application quickly by reading the architecture design and the decisions behind it, without reading code.

## Decision
Every significant decision is recorded as a short ADR in `docs/adr/`, numbered sequentially, using [template.md](template.md). ADRs are never edited after acceptance except for their status; a changed decision gets a new ADR that supersedes the old one. The [architecture design](../architecture/README.md) links to the ADRs that justify each part.

## Consequences
- Reading order for newcomers: architecture design → ADR index → specs.
- Pull requests that change a decision must add or supersede an ADR.

## Alternatives considered
- **Decisions only in the architecture document** – the "why" and the history get lost when the document is rewritten.
- **Wiki or issues** – separated from the code and its versions.
