# UILABEL: UI labels not matching the reference UI strings

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0005 (journey `reference`), ADR-0006, ADR-0007
- **Depends on:** INGEST, FIND

## Purpose
When a manual says "click **Submit Order**" but the button is called "Place Order", readers look for something
that does not exist. If the journey provides the application's real UI strings (`reference.ui_strings` in
`journey.yaml`, a JSON export of the localisation files), the `ui-labels` rule check compares every button,
menu and menu path the manuals name with that reference.

This spec covers labels against the reference. Labels that disagree between manuals without a reference are
left to the LLM tier.

## User stories
- As a documentation author, I want every UI label that does not exist in the application listed with the
  closest real label, so that I can correct it quickly.

## Behaviour
| Check id | Tier | Scope | Category |
|---|---|---|---|
| `ui-labels` | rule | page | `ui-label` |

- **Applies only** when the journey has `reference["ui_strings"]` (`applies_to` is false otherwise, so the
  check does not appear in such runs). An unreadable or invalid JSON file makes the check fail with an error
  row (the run continues).
- **Reference labels**: every non-empty string leaf of the JSON, recursively through objects and arrays; keys
  starting with `_` (comments) are skipped. Menu paths are normalised to `A › B › C`.
- **UI references in the manuals** (code blocks excluded), found per source line:
  - Bold text, `**X**`/`__X__` in Markdown and `<strong>`/`<b>` in HTML, that follows an action verb in the
    same sentence with at most 3 words in between (`click the **Save** button`). Verbs (any case): click,
    double-click, right-click, select, press, tap, choose, open, go to, navigate to, switch to (with -s/-ing
    forms). A sentence ends at `.`, `!`, `?`, `;` or `:`.
  - A bold label right after another detected label, separated only by "and", "or", "then" or a comma
    (`click **A** or **B**`).
  - Menu paths, always, with or without a verb: one bold text containing `›`, `>`, `→` or `->`, or bold parts
    separated by one of these (`**Admin** › **Users**`).
- **Comparison**:

| Case | Severity | Suggested fix |
|---|---|---|
| exact match (case-sensitive) of the label or the whole path | – (fine) | – |
| only a case-insensitive match | minor | "Did you mean 'Sign in'?" |
| no match | major | "Did you mean '…'?" when the closest label of the same kind (label vs. path) has WRatio ≥ 80 (≥ 90 for paths); else "Closest labels in the application: …" (up to two, WRatio ≥ 55); else use the exact label or update the reference |

  For menu paths the explanation also lists the segments that occur in no reference label or path
  ("Unknown menu entries: 'Settings'"), or says each entry exists but not as this path.
- All unknown labels on one line become one finding. The location quotes the label's markup
  (`**Submit Order**`, `<strong>Load</strong>`).

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-UILABEL-01 | the check registry; a journey without `ui_strings` | rule checks are listed / the check is asked whether it applies | `ui-labels` is registered with tier `rule`, scope `page`, category `ui-label`, and does not apply (and finds nothing) without the reference |
| AC-UILABEL-02 | a ui-strings JSON with nested objects, arrays and `_comment`/`_hidden` keys | the labels are loaded | all string leaves except those under `_` keys are labels |
| AC-UILABEL-03 | "Click **Submit Order**" (not in the reference) and "Click **Save**" (in it); each supported verb | `ui-labels` runs | one major finding for 'Submit Order' at its line quoting `**Submit Order**`, suggesting 'Place Order'; every verb is recognised |
| AC-UILABEL-04 | HTML with `<strong>` and `<b>` labels after "click" | `ui-labels` runs | unknown labels are reported with a "Did you mean" for a close match; bold text not after a verb ("becomes **Shipped**") is ignored |
| AC-UILABEL-05 | bold text without an action verb, or more than 3 words after it | `ui-labels` runs | no finding |
| AC-UILABEL-06 | menu paths: a known path (written with `›`, `>` or as separate bold parts), an unknown path, a path whose first entry is known but the rest not | `ui-labels` runs | only the unknown paths are reported; the explanation names the unknown entries and the fix names the closest real path |
| AC-UILABEL-07 | "Click **Sign In**" with reference "Sign in" | `ui-labels` runs | one minor finding with "Did you mean 'Sign in'?" |
| AC-UILABEL-08 | two unknown labels on one line | `ui-labels` runs | one finding naming both |
| AC-UILABEL-09 | "click **Nope**" inside a code block | `ui-labels` runs | no finding |
| AC-UILABEL-10 | the ShopFlow sample journey | the rule review runs | `ui-labels` reports at least one finding and all are verified |

## Examples
`samples/shopflow` (reference `reference/ui-strings.json`):
- `order-capturing/02-creating-an-order.md` line 47 "Click **Submit Order**" → *UI label 'Submit Order' not
  found in the application*; closest labels 'New Order' or 'Place Order'.
- `delivery/dispatch.html` line 24 "Click **Delivered**" → "Did you mean 'Mark as delivered'?".
- `notification/events.md` line 33 "Go to **Settings › Notifications › Templates**" → unknown entry
  'Settings'; closest path 'Admin › Notifications › Templates'.

## Out of scope
- UI references written without bold or quotes, or with the verb on a previous source line.
- Field names typed into ("In the **Customer** field") – not after an action verb.
- Comparing labels between manuals without a reference (LLM tier, TERM/CONSIST).

## Open questions
- Should "Preferences › Language" (first entry exists, sub-entry not in the export) be minor instead of major?
  The reference may not list every sub-menu.
