# TERM: Terminology drift and undefined terms

- **Status:** Implemented
- **Approval:** Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** PROMPT, LLM

## Purpose
Readers get confused when the same thing has several names, or when a product-specific term or acronym is
never explained. This LLM check finds both, across manuals and within a single manual.

## User stories
- As a technical writer, I want to see every concept that is named differently, with a quote per variant.
- As a new user, I want every product-specific term and acronym to be defined somewhere.

## Behaviour
| Property | Value |
|---|---|
| Check id | `terminology` |
| Tier / scope | LLM / journey, but applies to any journey with at least one manual |
| Categories | `terminology` (primary), `undefined-term` |

The instruction asks for (1) the same concept called by different names (one location per variant), ignoring
harmless synonyms; (2) product-specific terms, abbreviations and acronyms never defined in the manuals shown,
ignoring common industry words. The suggested fix names the term to standardise on or the definition to add.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-TERM-01 | the registry | lookup `terminology` | LLM tier, categories terminology and undefined-term |
| AC-TERM-02 | a one-manual journey | `applies_to` / run | applies; one call; `undefined_term` mapped to undefined-term |
| AC-TERM-03 | a journey | run | instruction covers different names for the same concept, one location per variant, undefined terms and acronyms |

## Out of scope
- A glossary file as reference input (could be added as a journey reference later).
