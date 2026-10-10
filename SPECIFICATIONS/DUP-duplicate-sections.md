# DUP: Duplicate and near-duplicate sections

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** INGEST (sections with line ranges and readable text), FIND

## Purpose
Copied sections drift apart when only one copy is updated, and readers cannot tell which one is current. The
`duplicates` rule check finds sections whose text is identical or nearly identical, on the same page, on
another page or in another manual of the journey.

## User stories
- As a documentation author, I want copied sections reported with both locations, so that I can keep the
  content in one place and link to it.

## Behaviour
| Check id | Tier | Scope | Category | Severity |
|---|---|---|---|---|
| `duplicates` | rule | manual | `duplicate` | minor |

- Scope is `manual` so the check also runs for one-manual journeys; it compares all sections of all pages of the
  journey, including across manuals and between Markdown and HTML.
- A section's **body** is its readable text (`Page.plain_lines`) from the line after its heading to the end of
  the section (subsections included). The heading itself is not compared, so the same text under a different
  heading is found.
- Normalisation: lower case, punctuation replaced by spaces, whitespace collapsed.
- Sections whose body has fewer than **20 words** are ignored.
- Similarity: `rapidfuzz.fuzz.ratio` on the normalised bodies; a pair with similarity **≥ 85** is a
  duplicate. Identical bodies give "Duplicate sections", others "Near-duplicate sections" with the similarity
  in the explanation.
- A section is never compared with its own parent or child.
- Pairs related by containment (a duplicated chapter and its duplicated subsections, or a parent whose text is
  mostly one duplicated child) form one group; one finding is reported per group: the pair with the highest
  similarity, on a tie the outer pair. A whole duplicated page is one finding.
- The finding has two locations, one per section, at the heading line, quoting the heading text (chosen so
  verification maps it back to that heading; empty if the heading text is not unique on the page).

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-DUP-01 | the check registry | rule checks are listed | `duplicates` is registered with tier `rule`, scope `manual`, category `duplicate` |
| AC-DUP-02 | two sections with identical body text under different headings on two pages | `duplicates` runs | one minor finding "Duplicate sections: …" with two locations at the two heading lines, quoting the headings |
| AC-DUP-03 | two sections ≥ 85 % similar in different manuals (Markdown and HTML) | `duplicates` runs | one "Near-duplicate sections" finding whose explanation gives the similarity and says "two different manuals" |
| AC-DUP-04 | sections with different text | `duplicates` runs | no finding |
| AC-DUP-05 | identical sections shorter than 20 words | `duplicates` runs | no finding |
| AC-DUP-06 | a parent section whose text is mostly its child; a whole page duplicated in two manuals | `duplicates` runs | parent and child are not reported against each other; the duplicated page gives one finding (the outer sections), not one per subsection |
| AC-DUP-07 | two identical sections with the same heading on the same page | `duplicates` runs | one finding whose two locations point to the two different heading lines and say "on the same page" |
| AC-DUP-08 | the ShopFlow sample journey | the rule review runs | `duplicates` reports at least one finding and all are verified |

## Examples
`samples/shopflow`: *Near-duplicate sections: '1.3 Adding products to the cart' and '2.2 Adding products to the
cart'* (`order-capturing/01-getting-started.md` line 18 and `02-creating-an-order.md` line 12, 93 % similar).

## Out of scope
- Paragraph-level duplicates inside otherwise different sections.
- Judging which copy is correct (the LLM tier compares content).
- Sections without a heading (text before the first heading).

## Open questions
- The thresholds (20 words, 85 %) are first guesses that separate the sample cleanly (93 % vs. 63 % next
  best); tune them in owner testing.
