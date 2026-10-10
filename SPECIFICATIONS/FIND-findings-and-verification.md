# FIND: Findings, quote verification and de-duplication

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.)
- **Related ADRs:** ADR-0007
- **Depends on:** INGEST

## Purpose
Give every check one finding format and make sure every quoted passage really exists in the manuals, so users can trust and locate each finding.

## Behaviour
- Quote matching order: exact on one line (readable text, then raw markup), exact across 2–6 consecutive lines, then fuzzy (partial ratio ≥ 90) over 1–3 lines. Whitespace, case and curly quotes are normalised; Markdown emphasis and link syntax are ignored.
- A location whose page cannot be resolved, or whose quote cannot be found, is unverified; a finding is verified only if all its locations are.
- Page ids given as `manual/path`, `path` only, or with leading slashes are resolved to the real page.
- Findings with the same fingerprint (category + locations) are reported once.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-FIND-01 | a finding whose quote appears verbatim in a page | it is verified | the location gets that line number and the finding is verified |
| AC-FIND-02 | a quote that spans two source lines | it is verified | the location gets the start and end line |
| AC-FIND-03 | a quote with different whitespace, case or Markdown emphasis | it is verified | it is still found |
| AC-FIND-04 | a quote with a small typo | it is verified | it is found by fuzzy matching |
| AC-FIND-05 | an invented quote | it is verified | the location and finding are marked unverified |
| AC-FIND-06 | a location with an unknown page | it is verified | the finding is unverified |
| AC-FIND-07 | a location given as a path without the manual id | it is verified | it is resolved to the right manual and page |
| AC-FIND-08 | two checks report the same category at the same locations | the run completes | the finding appears once |
