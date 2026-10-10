# INGEST: Load journeys and manuals

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing.)
- **Related ADRs:** ADR-0005
- **Depends on:** –

## Purpose
Turn manual folders on disk into a parsed corpus (pages, sections, links, anchors, images, code blocks, readable text, word counts) that keeps the original line numbers, so every check can point at real lines.

## User stories
- As a reviewer, I want to open a `journey.yaml` that lists related manuals, so that they are reviewed together.
- As a reviewer, I want to open a single manual folder, so that I can review one manual without writing a journey file.

## Behaviour
- A manual is a folder with `.md`, `.markdown`, `.html`, `.htm` files (recursive) and an optional `manual.yaml` (`id`, `title`, `version`, `entry`). Without `manual.yaml` the id and title are the folder name.
- A journey is a `journey.yaml` (`name`, `description`, `manuals` relative paths, `reference` map of relative paths).
- Markdown headings get GitHub-style anchors; duplicates get `-1`, `-2`. HTML anchors are `id` and `<a name>` attributes.
- `plain_lines` has one readable-text entry per source line (markup removed; code lines kept verbatim).
- Word counts exclude code blocks.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-INGEST-01 | a journey.yaml with three manual folders | it is loaded | the journey has the three manuals in the listed order with their pages |
| AC-INGEST-02 | a manual folder without manual.yaml | it is loaded | id and title are the folder name |
| AC-INGEST-03 | a Markdown page with headings | it is parsed | each heading becomes a section with its GitHub anchor, level and source line range |
| AC-INGEST-04 | a Markdown page with links and images | it is parsed | each link and image is recorded with target, source line and (for images) alt text or none |
| AC-INGEST-05 | an HTML page with ids, links, images and headings | it is parsed | anchors, links, images and sections are recorded with source line numbers |
| AC-INGEST-06 | a page with a fenced code block | it is parsed | the code block has its language, content and line range, and its words are not counted |
| AC-INGEST-07 | any page | it is parsed | `plain_lines` has exactly as many entries as the source has lines |
| AC-INGEST-08 | a journey.yaml with a missing manual folder, a missing reference file, invalid YAML, or duplicate manual ids | it is loaded | an `IngestError` names the file and the problem |
| AC-INGEST-09 | a folder that is a single manual (no journey.yaml) | `load_journey` is called on it | a one-manual journey is returned |

## Out of scope
PDF, DOCX and remote URLs.
