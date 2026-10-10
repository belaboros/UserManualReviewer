# ADR-0010: Compare two models by matching findings

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
The owner wants to compare the analysis of two LLMs side by side.

## Decision
A comparison takes two runs of the same journey and the same checks with different models (new or saved runs). Findings are matched when they have the same category and either overlapping locations (same page, overlapping lines) or quote similarity of at least 0.8. The result has three groups: **both**, **only A**, **only B**, plus each run's scores, tokens, cost and duration. Both runs execute concurrently when started together.

## Consequences
- Users see agreement, unique catches and likely hallucinations (unverified, only one model) at a glance.
- If an answer key exists (as for the samples), each run's recall and precision can be shown too.

## Alternatives considered
- **Two result windows next to each other without matching** – the user would have to match findings by eye.
- **An LLM to match findings** – costly and non-deterministic for a task that rules handle well.
