# ADR-0006: Two tiers of checks, rule-based and LLM-based

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Some problems are mechanical (a link to a missing file), others need understanding (two manuals disagree about when an order can be cancelled). LLM calls cost money and time and are not fully repeatable.

## Decision
Each check is a class with an id, a **tier** (`rule` or `llm`), a **scope** (`page`, `manual` or `journey`) and the categories it reports.
- **Rule checks** are deterministic Python over the parsed corpus and never call an LLM.
- **LLM checks** build a prompt from the corpus and a JSON schema, call the selected provider, and turn the answer into findings.
- Where useful, a rule check extracts candidates (numbers with units, defined terms, UI labels, status names) that an LLM check then judges, so the LLM sees less text.
- Prompts put the journey's manual text first, identically for every check, and the instruction last, so providers can cache the manuals.

## Consequences
- Rule findings appear instantly and cost nothing; a review with only rule checks works offline.
- The check list in the GUI shows which checks need an LLM.
- Side-by-side comparison only differs on LLM checks; rule findings are identical in both runs.

## Alternatives considered
- **Everything through the LLM** – expensive, slower, and LLMs miss mechanical issues such as a broken anchor more often than code does.
- **Rules only** – cannot find contradictions or journey gaps, which are the core of the request.
