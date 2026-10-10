# CONSIST: Inconsistencies within one manual, and step order logic

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** PROMPT, LLM

## Purpose
A single manual often states the same fact on several pages and gets out of step with itself: a timeout on
one page differs from another, a button is renamed on half the pages, a legacy feature is still described
after the manual says it was removed, a procedure uses something before it exists. Two LLM checks find these.

## User stories
- As a technical writer, I want a list of places where my manual disagrees with itself, with both quotes.
- As a technical writer, I want to know when a procedure's steps are in an order that cannot work.

## Behaviour
| Check id | Tier / scope | Categories (first = primary) |
|---|---|---|
| `consistency` | LLM / manual (one call per manual) | `inconsistency`, `value-conflict`, `stale-version`, `ui-label`, `malformed-code` |
| `procedures` | LLM / manual (one call per manual) | `step-order` |

Both checks send the per-manual corpus (spec PROMPT: only that manual plus the reference files), so the
two checks share the cached prefix for each manual. The instruction contains the scope note
"Review only the manual '<id>'".

`consistency` asks for: values given more than once (limits, sizes, timeouts, ports, URLs, file paths,
defaults, durations); the same UI element named differently or differing from the reference UI strings;
the same role/object/status named differently; changing identifiers and formats; conflicting commands, code
samples and configuration, template variables used versus documented, broken code blocks; references to
features the manual says were removed or are legacy; versions and dates that disagree or are outdated.
Only within the manual; differences to other manuals are out of scope (CONTRA).

`procedures` asks for steps that use something created or explained later, warnings or prerequisites placed
after the action they should precede, saving before data is entered, and wrong step cross-references; not
numbering typos (rule check STRUCT) or optional steps.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-CONSIST-01 | the registry | lookup `consistency` | LLM tier, manual scope, the five categories, inconsistency primary; applies to one-manual journeys |
| AC-CONSIST-02 | a journey with two manuals | run `consistency` | two calls, each with only that manual's corpus and the scope note |
| AC-CONSIST-03 | the instruction | inspect | covers values, ports, paths, timeouts, UI elements, roles, formats, commands, template variables, removed/legacy features, versions, the reference block, and lists the five categories |
| AC-CONSIST-04 | a canned answer for one manual | run | findings mapped to that manual's page and category |
| AC-CONSIST-05 | the registry and a canned answer | run `procedures` | LLM tier, manual scope, `step-order` only (unknown categories mapped to it); instruction covers later-created items and late warnings |
| AC-CONSIST-06 | `consistency` and `procedures` on the same journey | run both | identical `cache_prefix` per manual |

## Examples
Page 1: "Your session ends after 15 minutes of inactivity." Page 4: "sessions time out after 30 minutes" →
`value-conflict` with two quotes.

## Out of scope
- Step numbering gaps and duplicates (rule check STRUCT).
- Syntax validation of JSON/YAML/CSV blocks (rule check CODE); the LLM judges conflicts and obvious breakage.
