# CONTRA: Contradictions across manuals

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** PROMPT, LLM

## Purpose
Related manuals are written by different teams and drift apart. A reader who follows two manuals should not
find statements that cannot both be true. This LLM check finds them and quotes both sides.

## User stories
- As a documentation lead, I want to see every pair of statements in different manuals that contradict each
  other, with both quotes, so I can decide which manual to fix.

## Behaviour
| Property | Value |
|---|---|
| Check id | `contradictions` |
| Tier / scope | LLM / journey (applies when the journey has 2+ manuals) |
| Categories | `contradiction` (primary), `value-conflict` |
| Prompt | shared corpus first (spec PROMPT), then the contradictions instruction |

The instruction asks the model to compare the manuals topic by topic: statuses and transitions, roles and
permissions, timings and deadlines, limits and values, flows and hand-offs, channels and opt-in/opt-out rules,
and features one manual calls available and another removed. `value-conflict` is used when only a value
differs, `contradiction` when the meaning conflicts. More detail in one manual, or statements about
clearly different situations, are not contradictions.

Every finding must have locations in at least two different manuals; findings that do not are dropped.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-CONTRA-01 | the check registry | lookup `contradictions` | LLM tier, journey scope, categories contradiction and value-conflict; applies to 2+ manuals only |
| AC-CONTRA-02 | a journey | run | one call: corpus as cache prefix, then an instruction listing the topics, the allowed categories and the two-manual rule |
| AC-CONTRA-03 | answers with locations in two manuals, one manual twice, and a single location | run | only the finding with two different manuals is kept |
| AC-CONTRA-04 | answers with `value-conflict` and an unrelated category | run | value-conflict kept, unrelated mapped to contradiction; source is the provider name |

## Examples
Manual A: "An order can be cancelled while it has the status Paid." Manual B: "Once an order is Paid it can
no longer be cancelled." → one `contradiction` finding with both quotes.

## Out of scope
- Contradictions within one manual (CONSIST).
- Deciding which manual is right.
