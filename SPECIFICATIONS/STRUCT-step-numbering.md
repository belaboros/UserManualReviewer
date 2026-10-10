# STRUCT: Step numbering

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** INGEST, FIND

## Purpose
Numbered procedures that skip a number (1, 2, 3, 5) usually lost a step; repeated numbers (1, 2, 3, 3) show
that steps were inserted or reordered without care. The `numbering` rule check finds these mechanical
numbering problems. Whether the steps are in a *logical* order is judged by the LLM tier.

## User stories
- As a reader following a procedure, I want numbering gaps reported, so that no step is silently missing.

## Behaviour
| Check id | Tier | Scope | Category |
|---|---|---|---|
| `numbering` | rule | page | `step-order` |

- **Markdown**: ordered lists are read with markdown-it (CommonMark) from the page source, so the numbers are
  the ones the author typed (`1.` or `1)`), code blocks are excluded and nested lists are separate lists.
  Items separated by blank lines or indented continuation text stay in one list.
- **HTML**: `<ol>` items carry no typed numbers and are not checked (explicit `value` attributes are out of
  scope). Lines whose readable text starts with a typed number (`^\d+[.)]\s`) are checked as a list when they
  follow each other, with only empty lines between; any other text ends the list. Lines inside headings and
  code blocks are ignored.
- Within a list, each item is compared with the previous one:

| Previous → current | Title | Severity |
|---|---|---|
| n → n + 1 | (fine) | – |
| n → n | "Step number n is used twice" | minor |
| n → m, m > n + 1 | "Step numbering skips from n to m" (names the missing numbers) | major, a step may be missing |
| n → m, m < n | "Step numbering goes back from n to m" | minor |

- Lists with fewer than two items, and lists where every item has the same number (the "1. 1. 1." convention)
  are not reported. A list may start at any number.
- One finding per break, located at the offending item's line, quoting its text.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-STRUCT-01 | the check registry | rule checks are listed | `numbering` is registered with tier `rule`, scope `page`, category `step-order` |
| AC-STRUCT-02 | a Markdown list numbered 1, 2, 3, 5 | `numbering` runs | one major finding "Step numbering skips from 3 to 5" saying step 4 is missing, at the line of item 5 |
| AC-STRUCT-03 | a list numbered 1, 2, 3, 3 | `numbering` runs | one minor finding "Step number 3 is used twice" at the second 3 |
| AC-STRUCT-04 | a list numbered 1, 2, 3, 2 | `numbering` runs | one finding "Step numbering goes back from 3 to 2" |
| AC-STRUCT-05 | correct lists, a list with continuation paragraphs, a list starting at 4, a 1, 1, 1 list | `numbering` runs | no finding |
| AC-STRUCT-06 | nested lists and numbered lines inside a code block | `numbering` runs | each nested list is checked on its own; code is ignored |
| AC-STRUCT-07 | an HTML page with typed numbers 1, 2, 4 in paragraphs, an `<ol>` and numbered headings | `numbering` runs | one finding for the skip; the `<ol>` and headings give none |
| AC-STRUCT-08 | a list 1, 2, 2, 5, 6 | `numbering` runs | two findings (repeat at the second 2, skip from 2 to 5), each at its own line |
| AC-STRUCT-09 | the ShopFlow sample journey | the rule review runs | `numbering` reports at least one finding and all are verified |

## Examples
`samples/shopflow`:
- `order-capturing/02-creating-an-order.md` line 47 `5. Click **Submit Order**.` → *Step numbering skips from
  3 to 5* (major).
- `notification/events.md` line 36 → *Step number 3 is used twice* (minor).

## Out of scope
- Logical order of steps (LLM tier), lettered lists, HTML `<ol start>`/`<li value>`.

## Open questions
- None.
