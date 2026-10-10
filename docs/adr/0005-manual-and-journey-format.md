# ADR-0005: Manuals are folders with `manual.yaml`; a journey is a `journey.yaml`

- **Status:** Proposed
- **Date:** 2026-10-10

## Context
Manuals are local `.md` or `.html` files, often several pages per manual. Several manuals together form one end-to-end user journey, and some checks need reference data (for example the real UI labels).

## Decision
- A **manual** is a folder containing `.md`, `.markdown`, `.html` or `.htm` files (found recursively) and a `manual.yaml`:
  ```yaml
  id: order-capturing        # optional, defaults to the folder name
  title: ShopFlow Order Capturing
  version: "3.4"             # optional, used by version checks
  entry: index.md            # optional, start page for orphan detection
  ```
- A **journey** is a `journey.yaml` that lists manuals and optional reference files:
  ```yaml
  name: ShopFlow order to delivery
  description: A customer order from capture to delivery, with notifications.
  manuals: [manuals/order-capturing, manuals/delivery, manuals/notification]
  reference:
    ui_strings: reference/ui-strings.json
    glossary: reference/glossary.md
  ```
- A single manual can be reviewed without a journey; the GUI creates an in-memory journey for it.
- Every page keeps its original line numbers so findings point to real lines; HTML is mapped back to source lines.

## Consequences
- Journeys are versionable and shareable next to the manuals.
- Cross-manual and journey checks only run when a journey has two or more manuals.

## Alternatives considered
- **Single files only** – real manuals are multi-page.
- **Inferring journeys automatically** – unreliable; the user knows which manuals belong together.
