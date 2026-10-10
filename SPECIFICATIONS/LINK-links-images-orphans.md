# LINK: Broken links and anchors, missing images and alt text, orphan pages

- **Status:** Implemented (Approved by the owner's go-ahead on 2026-10-10; to be validated in owner testing)
- **Related ADRs:** ADR-0005, ADR-0006, ADR-0007
- **Depends on:** INGEST (pages with links, anchors and line numbers), FIND (verification)

## Purpose
Readers of a manual follow links between pages and between manuals. A link to a missing page, an anchor that
does not exist, a broken image or a page nobody links to are mechanical problems that code finds reliably and
for free. These rule checks report them with the exact line and markup.

## User stories
- As a documentation author, I want every broken link and anchor listed with its line, so that I can fix them
  before publishing.
- As a reviewer, I want missing screenshots and images without alt text reported, so that the manual is
  complete and accessible.
- As a maintainer, I want pages that nothing links to reported, so that I can link or delete them.

## Behaviour

Three rule checks (tier `rule`, never call an LLM):

| Check id | Scope | Categories | Finds |
|---|---|---|---|
| `links` | manual | `broken-link`, `broken-anchor` | relative links to files that do not exist; `#anchors` missing on the target page |
| `images` | page | `image` | image files that do not exist; images without alt text |
| `orphans` | manual | `orphan-page` | pages no other page links to that are not the manual's entry page |

`links` and `orphans` use scope `manual` (not `journey`) so they also run on one-manual journeys; links into
other manuals are still followed.

**Link resolution**
- Ignored as external: any href with a URL scheme (`http:`, `https:`, `mailto:`, `ftp:`, `tel:` …) or starting
  with `//`; the placeholder `#`.
- The path part (before `#`, without `?query`, URL-decoded) is resolved relative to the linking page's folder;
  a path starting with `/` is resolved relative to the manual root.
- The file must exist on disk. Links may leave the manual (for example `../delivery/index.html`) and are fine
  when the file exists.
- An empty href (`[text]()`) is a broken link.
- Anchors: `#x` is checked on the same page, `file#x` on the target page when it is a page of the journey. Valid
  anchors are `Page.anchors` (GitHub-style heading slugs for Markdown, `id`/`name` attributes for HTML), any
  `id="…"`/`name="…"` attribute in the page source (raw HTML in Markdown), and `top`. Anchors are case-sensitive.
  Anchors into files that are not pages of the journey (PDF, images) are not checked.

**Severities and fixes**

| Problem | Category | Severity | Suggested fix |
|---|---|---|---|
| Link to a missing file, or empty link | `broken-link` | major | "Did you mean '…'?" when a file in the target folder has a similar name (ratio ≥ 75), else create the page or fix/remove the link |
| Missing anchor | `broken-anchor` | minor (the reader still reaches the page) | case-only match: use the exact case; similar anchor (WRatio ≥ 80, ignoring numbering prefixes like `12-`): "Did you mean '#…'?"; HTML heading without `id` whose text matches: add `id="…"` to that heading |
| Missing image file | `image` | major | add the file or correct the path |
| Image without alt text | `image` | minor | add descriptive alt text |
| Missing image file without alt text | `image` | major, one finding | both |
| Orphan page | `orphan-page` | minor | link to it (from the entry page) or delete it |

- HTML `<img alt="">` (an explicit empty alt) marks a decorative image and is not reported for alt text. In
  Markdown `![](x.png)` has no alt text.
- External image URLs are not downloaded; only their alt text is checked.
- Several problems of the same category on one line become one finding, because findings are de-duplicated by
  category and location (ADR-0007 fingerprint).

**Orphans**
- A page is linked when any other page of the journey (any manual) has a non-image link that resolves to it.
  Links from a page to itself do not count.
- The entry page is never an orphan: `entry` from `manual.yaml`, else `index.md`/`index.markdown`/
  `index.html`/`index.htm`/`README.md` at the manual root, else the alphabetically first page at the root.
- Manuals with only one page are not checked.
- The location is the page's first non-empty line (usually the title).

**Locations**: every finding has `source="rule"`, `confidence=1.0` and a location with `manual_id`,
`page_path`, the line and a short verbatim quote: the link or image markup (`[Text](x.md)`,
`<a href="x.html">`), the target, or the line text, chosen so that quote verification maps it back to the same
line. When no text on the line is unique on the page, the quote is left empty and the line number is kept.

## Acceptance criteria
| Id | Given | When | Then |
|---|---|---|---|
| AC-LINK-01 | the check registry | rule checks are listed | `links` (manual, broken-link + broken-anchor), `images` (page, image) and `orphans` (manual, orphan-page) are registered with tier `rule` |
| AC-LINK-02 | a Markdown or HTML link to a file that does not exist, or an empty link | `links` runs | one major `broken-link` finding at the link's line, quoting the link markup |
| AC-LINK-03 | links to existing pages and the placeholder `#` | `links` runs | no finding for them |
| AC-LINK-04 | an in-page link `#x` where the page has no anchor `x` (Markdown slug or HTML id) | `links` runs | one minor `broken-anchor` finding; existing in-page anchors give none |
| AC-LINK-05 | a link `page#x` where the target page lacks anchor `x` | `links` runs | one `broken-anchor` finding naming `#x`; existing anchors on that page give none |
| AC-LINK-06 | links into another manual of the journey, in a multi-manual or a one-manual journey | `links` runs | they resolve when the file exists, missing files and anchors there are reported, and the check applies to one-manual journeys |
| AC-LINK-07 | `http(s):`, `mailto:`, other schemes and `//host` links | `links` runs | they are ignored |
| AC-LINK-08 | a broken link with a similarly named existing file, an anchor differing only in case, an HTML heading without id matching the anchor | `links` runs | the suggested fix names the file, the correct-case anchor, or says to add the id |
| AC-LINK-09 | two broken links on the same line | `links` runs | one finding naming both targets |
| AC-LINK-10 | an image whose file does not exist (with alt text) | `images` runs | one major `image` finding "Missing image '…'"; existing images with alt text give none |
| AC-LINK-11 | an image without alt text (Markdown `![](…)`, HTML `<img>` without `alt`) | `images` runs | one minor `image` finding; HTML `alt=""` is not reported for alt text |
| AC-LINK-12 | a missing image file without alt text | `images` runs | exactly one major finding mentioning both problems |
| AC-LINK-13 | an external image URL without alt text | `images` runs | only the alt-text finding (minor), no missing-file finding |
| AC-LINK-14 | a page no other page links to | `orphans` runs | one minor `orphan-page` finding at the page's first line |
| AC-LINK-15 | the manual's entry page (from `manual.yaml`, else `index.*`) | `orphans` runs | it is never reported; `entry` wins over `index.*` |
| AC-LINK-16 | a page linked only from another manual, and a page linked only from itself | `orphans` runs | the first is not an orphan, the second is |
| AC-LINK-17 | a manual with a single page | `orphans` runs | no finding |
| AC-LINK-18 | any finding of `links`, `images`, `orphans` | quote verification runs | the finding is verified and keeps the line number the check reported |
| AC-LINK-19 | the ShopFlow sample journey | `ReviewService().review(journey, ["rules"])` runs | no check errors; `links`, `images` and `orphans` report findings and every rule finding is verified |

## Examples
From `samples/shopflow`:
- `delivery/index.html` line 12: `<a href="dispatch.htm">` → *Broken link to 'dispatch.htm'*, fix "Did you mean
  'dispatch.html'?".
- `order-capturing/04-troubleshooting.md` line 13: `[Logging in](01-getting-started.md#logging-in-to-shopflow)` →
  *Broken anchor '#logging-in-to-shopflow'*, fix "Did you mean '#12-logging-in'?".
- `notification/events.md` line 40: `../delivery/dispatch.html#failed-delivery` → broken anchor; the HTML heading
  "2.3 Failed delivery" has no id, so the fix says to add `id="failed-delivery"`.
- `delivery/picking.html` line 11: `<img src="images/picking-queue.png">` → *Missing image … without alt text*.
- `notification/legacy-sms.md` → *Orphan page 'legacy-sms.md'*.

## Out of scope
- Checking external URLs (no network access in rule checks).
- Reachability from the entry page through chains of links (a page linked only from another orphan is not
  reported).
- HTML `<link>`, `<script>` and CSS references; Markdown reference-style link definitions that are never used.

## Open questions
- Should a broken anchor be major instead of minor? Chosen minor because the reader still reaches the page.
