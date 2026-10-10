# PROMPT: Prompt building, response mapping, context budget and caching layout

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0006, ADR-0007, ADR-0003
- **Depends on:** LLM, INGEST, FIND

## Purpose
All LLM checks send the manuals in the same way, ask for the same finding structure, and turn the answer
into verified-quote findings. The manuals block is identical for every check of a run so providers can cache
it, and large manual sets are split automatically when they do not fit the model's context.

## User stories
- As a reviewer, I want every LLM finding to point at an exact page and a verbatim quote, so I can check it.
- As a cost-conscious reviewer, I want the manuals sent once and cached across checks.
- As a reviewer with a small local model, I want large manual sets to be split rather than fail.

## Behaviour

### Corpus block (`umr.checks.llm.prompting.render_corpus(journey, manuals=None, pages=None)`)
Deterministic text (same input, byte-identical output):
1. `JOURNEY: <name>`, `DESCRIPTION: <description>` (whitespace collapsed), `MANUALS:` with one line per
   included manual (`- <id>: <title> (version <v>, <n> pages)`).
2. Reference files of the journey (`.json`, `.yaml`, `.yml`, `.txt`, `.md`, `.csv`, ≤ 100 000 characters),
   each headed `=== REFERENCE <key>: <file name> (ground truth, not part of the manuals) ===`.
3. Every page in manual order, headed `=== PAGE <manual_id>/<page_path> (manual: <title>, version <v>) ===`,
   then the page's readable text (`plain_lines`), with runs of empty lines collapsed to one; for Markdown
   pages the heading marker and list marker (including the step number) of the source line are kept.

### Prompt layout
- System prompt `SYSTEM_PROMPT`, shared by all checks: expert documentation reviewer; only real problems;
  each location has the exact page id from the header and a 5–25 word quote copied exactly; no invented
  quotes; `{"findings": []}` when nothing is found.
- `cache_prefix` = the corpus block; `prompt` = the check instruction (`TASK`, the check's text, the allowed
  categories, an optional scope note, the JSON shape). The corpus always comes first.
- One response schema for every check (`FindingsResponse`), so the schema never differs between checks:
  `{"findings":[{"category","severity","title","explanation","suggested_fix","confidence","locations":[{"page","quote"}]}]}`.
  Severity accepts synonyms (high→major, medium/low→minor, blocker→critical, note→info; unknown→minor);
  confidence given as a percentage is scaled to 0–1.

### Mapping to findings
`to_findings` creates domain `Finding`s with `check_id`, `source = provider.name`, `verified = False`
(verification happens in `ReviewService`), and `Location(manual_id, page_path, quote)`. The page id is matched
against the journey's pages; otherwise it is split at the manual id prefix or the first `/`. Header decorations
(`=== PAGE`, `(manual: …)`, backticks) are stripped. A category is matched by value or name (case, `_` and
spaces ignored); an unknown category, or one the check does not report, becomes the check's first (primary)
category. Findings without any location are dropped. Identical findings (category and quoted locations) from
several calls are merged.

### Context budget
A call fits when the estimated tokens (characters / 4) of system prompt + corpus + instruction are at most
70 % of `context_tokens`. Otherwise:
- journey-scope checks run once per pair of manuals (scope note "you see only '<a>' and '<b>'"); a pair that
  does not fit, or a one-manual journey that does not fit, runs per page group;
- manual-scope checks run once per manual (always), and per page group if one manual does not fit;
- page groups are packed greedily in page order; a single page that is too big is sent alone.
Results of all calls are merged.

### Errors and statistics
Each call goes through `complete_validated` (spec LLM): its usage is added to `ctx.usage` and its outcome to
`ctx.llm_stats`. A call that still fails after the retry raises `LlmError`; the check reports no findings and
`ReviewService` records an error row for it; other checks continue.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-PROMPT-01 | a journey | `render_corpus` twice | identical text with the journey header and one `=== PAGE <manual>/<path> (manual: <title>, version <v>) ===` header per page in manual order |
| AC-PROMPT-02 | pages with markup and empty lines | `render_corpus` | readable text, empty runs collapsed, Markdown step numbers kept |
| AC-PROMPT-03 | a journey with a reference file / a subset | `render_corpus` | reference block before the pages / only the selected manuals or pages |
| AC-PROMPT-04 | several journey checks on the same journey | run | same system prompt and identical `cache_prefix` (the corpus) for all; instruction only in `prompt` |
| AC-PROMPT-05 | a valid JSON answer | `to_findings` | findings with check id, source, severity, confidence, fix and locations split into manual id and page path |
| AC-PROMPT-06 | an unknown or disallowed category, a severity synonym, a percentage confidence | mapping | primary category; normalised severity and confidence |
| AC-PROMPT-07 | a finding without locations | run | dropped |
| AC-PROMPT-08 | a journey check whose full corpus exceeds 70 % of `context_tokens` but pairs fit | run | one call per manual pair, with a scope note; results merged and de-duplicated |
| AC-PROMPT-09 | one manual too big (manual scope), or a one-manual journey too big | run | one call per page group |
| AC-PROMPT-10 | a provider that answers invalid JSON twice for one check | `ReviewService.review` | that check has an error row, the other checks complete, `llm_stats` and usage aggregated; valid quotes are verified |
| AC-PROMPT-11 | all LLM checks | run | one shared response schema |
| AC-PROMPT-12 | a check run (or a run without a provider) | after the run | `ctx.usage` and `ctx.llm_stats` contain every call (without a provider the check raises `LlmError`) |

## Examples
```
JOURNEY: ShopFlow order to delivery
DESCRIPTION: A customer order from capture through picking, packing, dispatch and delivery, ...
MANUALS:
- order-capturing: ShopFlow Order Capturing (version 3.4, 6 pages)
...
=== PAGE order-capturing/01-getting-started.md (manual: ShopFlow Order Capturing, version 3.4) ===
# 1. Getting started
## 1.2 Logging in
1. Open https://shopflow.example.com/oms.
```

## Out of scope
- Exact tokenisation (the estimate is characters / 4).
- Splitting a single oversized page.
- Rule-tier candidate extraction feeding the LLM (ADR-0006 mentions it as an option).

## Open questions
- HTML ordered lists lose their numbers in `plain_lines` (ingest); the corpus could add them later.
