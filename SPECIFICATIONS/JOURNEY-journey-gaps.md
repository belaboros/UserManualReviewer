# JOURNEY: Gaps in the end-to-end journey

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** PROMPT, LLM

## Purpose
The manuals of a journey together must let a reader get from the first step to the last. Each manual may be
fine on its own while the hand-offs between them are undocumented. This LLM check walks the journey and
reports where a reader gets stuck.

## User stories
- As a product owner, I want to know which steps, hand-offs, prerequisites and error paths of the journey no
  manual explains, so I can assign them to a manual.

## Behaviour
| Property | Value |
|---|---|
| Check id | `journey` |
| Tier / scope | LLM / journey (2+ manuals) |
| Categories | `journey-gap` (primary), `prerequisite`, `missing-error-path` |

The instruction asks the model to walk the journey named in the corpus header and report: undocumented
hand-offs between manuals or systems; events, messages, statuses or states that one manual mentions and no
manual defines, produces or owns; missing middle steps; prerequisites (roles, devices, add-ons, accounts,
configuration, data) required but never explained how to obtain; missing error and recovery paths.
Contradictions are left to CONTRA.

Each finding needs at least one location: the quote of the sentence that creates the expectation or shows the
gap (so it can be verified, ADR-0007). Findings without a location are dropped.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-JOURNEY-01 | the registry | lookup `journey` | LLM tier, journey scope, the three categories; 2+ manuals |
| AC-JOURNEY-02 | answers with one location, none, and a category spelled "journey gap" | run | single-location findings kept, the location-less one dropped, category normalised |
| AC-JOURNEY-03 | a journey | run | the instruction covers hand-offs, events, states, prerequisites and how to obtain them, error and recovery paths, and quoting the sentence that creates the expectation; the corpus starts with the journey name and description |

## Examples
Manual A: "When the order ships, the customer is notified." No manual defines a "shipped" notification →
`journey-gap` located at that sentence.

## Out of scope
- Journey gaps without any quotable location (would be unverifiable).
