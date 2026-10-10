# CODE: Malformed code blocks

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0006, ADR-0007
- **Depends on:** INGEST (code blocks with language and line range), FIND

## Purpose
Readers copy configuration and data examples from manuals. A JSON example with a trailing comma or a CSV
example whose rows do not match the header fails as soon as it is used. The `code` rule check parses JSON,
YAML and CSV examples and reports the ones that are malformed, at the line of the error.

This spec covers the rule tier only; "conflicting commands" (FEATURES.md) are judged by the LLM tier.

## User stories
- As a reader, I want examples that work when I copy them, so that I do not lose time on syntax errors.

## Behaviour
| Check id | Tier | Scope | Category | Severity |
|---|---|---|---|---|
| `code` | rule | page | `malformed-code` | major |

Which blocks are checked (Markdown fences and indented blocks, HTML `<pre>`, language from the fence info or a
`language-…` class):

| Kind | Detected by | Parsed with | Error line |
|---|---|---|---|
| JSON | language `json`, or no language and content starting with `{` or `[` (unless it contains `...` or `…`, an elided example) | `json.loads` | the line `JSONDecodeError` reports |
| YAML | language `yaml` or `yml` | `yaml.safe_load_all` | the problem mark's line |
| CSV | language `csv` (delimiter detected from the header: `,` `;` tab or `|`, whichever occurs most) or `tsv` (tab) | `csv.reader` (quoted fields respected) | every data row whose column count differs from the header |

- Blocks containing template placeholders (`{{`, `{%`, `<%`) and blocks in other languages are not checked.
- Error lines are source lines: for a Markdown fence the content starts on the line after the fence; for HTML
  `<pre>` the content starts on the `<pre>` line.
- JSON explanations add a hint for the common cases: "probably a trailing comma before a closing bracket",
  "probably a missing comma".
- JSON/YAML: one finding per block at the error line. CSV: one finding per block, with one location per bad
  row (at most 5) and the explanation listing every bad row with its column count.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-CODE-01 | the check registry | rule checks are listed | `code` is registered with tier `rule`, scope `page`, category `malformed-code` |
| AC-CODE-02 | a `json` block with a trailing comma, and a valid `json` block | `code` runs | one major finding "Malformed JSON code block" at the line of the error, mentioning the trailing comma; the valid block gives none |
| AC-CODE-03 | blocks without a language: one starting with `[` that is invalid, one with `...`, one with plain text | `code` runs | only the first is reported |
| AC-CODE-04 | an invalid `yaml` block and a valid `yml` block | `code` runs | one finding "Malformed YAML code block" located inside the invalid block |
| AC-CODE-05 | a `csv` block with a `;` header of 4 columns and rows with 3 and 5 columns; blocks with quoted commas, a `tsv` block and a tab-separated `csv` block with a short row | `code` runs | one finding per malformed block naming the delimiter, with a location for each bad row; quoted delimiters do not count as separators |
| AC-CODE-06 | a `json` block with `{{ placeholders }}`, a `python` block, an unlabelled template | `code` runs | no finding |
| AC-CODE-07 | an HTML `<pre><code class="language-json">` block with a missing comma | `code` runs | one finding at the source line of the error, mentioning the missing comma |
| AC-CODE-08 | the ShopFlow sample journey | the rule review runs | `code` reports at least one finding and all are verified |

## Examples
`samples/shopflow`:
- `notification/channels.md` lines 23–31: the `json` example has a trailing comma after `"port": 587` →
  *Malformed JSON code block* at line 28.
- `order-capturing/05-bulk-import.md`: the `csv` example's header has 4 semicolon-separated columns, line 10
  has 3 and line 11 has 5 → one finding with two locations.

## Out of scope
- Shell commands, SQL and other languages; JSON with comments (`jsonc`, `json5`); semantic validation against a
  schema; inline code spans.

## Open questions
- None.
