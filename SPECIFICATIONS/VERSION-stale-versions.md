# VERSION: Stale version mentions

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0005 (`version` in `manual.yaml`), ADR-0006, ADR-0007
- **Depends on:** INGEST, FIND

## Purpose
A chapter that says "this chapter describes ShopFlow 3.2" inside a manual for 3.4 was probably not updated.
The `versions` rule check reports bare claims of a product version that differs from the manual's version.
It deliberately ignores versions mentioned as history, future plans or ranges, which are normal in manuals.

## User stories
- As a documentation author, I want passages that still claim an old product version reported, so that I can
  review and update them.

## Behaviour
| Check id | Tier | Scope | Category | Severity |
|---|---|---|---|---|
| `versions` | rule | manual | `stale-version` | minor |

- Applies only when at least one manual of the journey has `version` set; manuals without a version are not
  checked.
- **Product names** are guessed from the first word of each manual title and of the journey name when it is
  capitalised, longer than 2 characters and not a stop word ("The", "User", …). For ShopFlow: `ShopFlow`.
- **Version claims** are searched in the readable text of each page (code blocks excluded), sentence by
  sentence, with these patterns (`X.Y` is a dotted version such as `3.2` or `3.2.1`):

| Pattern | Example |
|---|---|
| `<Product> X.Y` | "the order flow in ShopFlow 3.2" |
| `version X.Y` | "this guide covers version 3.1" |
| `vX.Y` (not inside a path like `/api/v1.2`) | "screens from v4.0" |

- **Heuristic: context that is not a claim.** A mention is ignored when
  - its sentence contains a historical, future or range word: removed, deprecated, introduced, added, new,
    changed, since, before, prior, earlier, older, previous(ly), legacy, planned, upcoming, future, will, until,
    after, later, newer, upgrade, migrate, replaced, no longer, starting, onwards, from, as of, up to, above,
    below, minimum, at least, require(d/s), compatible, (un)supported, released, release notes, was, were,
    used to;
  - the version is a range or wildcard (`2.x`, `3.*`) or a minimum (`3.2+`);
  - "version X.Y" is preceded by a capitalised word that is not a product name ("Python version 3.12").
- A mention matches the manual's version when one is a prefix of the other part by part (`3.4` matches `3.4`
  and `3.4.2`). Other mentions are reported, all mentions of one line in one finding. The explanation says
  "an older version" when every mention is lower than the manual's version, else "a different version".
- The location quotes the matched phrase ("ShopFlow 3.2").

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-VERSION-01 | the check registry; a journey whose manuals have no `version` | rule checks are listed / the check is asked whether it applies | `versions` is registered with tier `rule`, scope `manual`, category `stale-version`, and does not apply without versions |
| AC-VERSION-02 | manual version 3.4 and the sentence "describes the order flow in Acme 3.2" (title "Acme Ordering") | `versions` runs | one minor finding naming 'Acme 3.2' and 3.4, saying "older version", quoting "Acme 3.2" at that line |
| AC-VERSION-03 | "covers version 3.1", "show v4.0", "See v3.4" | `versions` runs | findings for 3.1 and 4.0 ("different version"), none for v3.4 |
| AC-VERSION-04 | "Version: Acme 3.4", "Acme 3.4.2 fixes a bug", "This is version 3.4." | `versions` runs | no finding |
| AC-VERSION-05 | "removed in Acme 3.0", "planned for Acme 4.0", "Acme 2.x", "Requires Acme 3.2+", "Since version 3.1", "Upgrade from Acme 3.3" | `versions` runs | no finding |
| AC-VERSION-06 | "Chrome 120", "Python version 3.12", versions inside a code block, `/api/v1.2/` | `versions` runs | no finding |
| AC-VERSION-07 | two manuals with the same stale claim, only one with a `version` | `versions` runs | only the manual with a version is reported |
| AC-VERSION-08 | two stale mentions on one line | `versions` runs | one finding naming both |
| AC-VERSION-09 | the ShopFlow sample journey | the rule review runs | `versions` reports at least one finding and all are verified |

## Examples
`samples/shopflow`: `order-capturing/02-creating-an-order.md` line 3 "This chapter describes the full order
capturing flow in ShopFlow 3.2." (manual version 3.4) → *Version mention 'ShopFlow 3.2' differs from the manual
version 3.4*. Not reported: "removed in ShopFlow 3.0", "ShopFlow 2.x sent SMS", "planned for 4.0".

## Out of scope
- Dates ("Last updated: March 2022"), versions of other products, and inconsistent versions between manuals
  (CONSIST, LLM tier).
- Product names that are not the first word of a manual title.

## Open questions
- The context word list is a heuristic; mentions that are claims but share a sentence with a context word
  ("ShopFlow 3.2 was installed") are missed by design. Owner testing should show whether it is too broad.
