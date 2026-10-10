# ADR-0007: One finding schema, with quotes verified against the source

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Users act on findings, so each one must be checkable. LLMs sometimes paraphrase or invent text.

## Decision
All checks report the same `Finding` structure:

| Field | Meaning |
|---|---|
| `check_id`, `category` | which check and which kind of problem |
| `severity` | `critical`, `major`, `minor`, `info` |
| `title`, `explanation`, `suggested_fix` | human-readable text |
| `locations[]` | `manual_id`, `page_path`, `line_start`, `line_end`, `quote` |
| `source` | `rule` or the provider name |
| `confidence` | 0–1, rule findings are 1 |
| `verified` | true if every quote was found in the source |
| `fingerprint` | stable hash of category and locations, for de-duplication and comparison |

LLMs return quotes, not line numbers. The application finds each quote in the source (exact, then whitespace-normalised, then fuzzy with a similarity of at least 0.9) and fills in the line numbers. A finding with an unmatched quote is kept but marked unverified, shown greyed out, and excluded from the score.

## Consequences
- The GUI can always jump to and highlight the exact passage.
- Hallucinated findings are visible as such instead of silently lowering the score.
- Journey gaps may legitimately have no location; they are verified when the check explains which steps are missing.

## Alternatives considered
- **Trusting LLM line numbers** – models count lines unreliably.
- **Dropping unverified findings** – hides useful signal and makes model comparison less informative.
