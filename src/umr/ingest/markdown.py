"""Parse a Markdown file into a Page with source line numbers."""

from pathlib import Path

from markdown_it import MarkdownIt

from umr.domain import CodeBlock, Link, Page, Section
from umr.ingest.slug import github_slug
from umr.ingest.text import count_words, markdown_line_to_text

_md = MarkdownIt("commonmark").enable("table")


def parse_markdown(manual_id: str, rel_path: str, abs_path: Path) -> Page:
    source = abs_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    tokens = _md.parse(source)

    headings: list[tuple[int, str, int]] = []  # (level, text, line)
    links: list[Link] = []
    code_blocks: list[CodeBlock] = []
    in_fence: set[int] = set()

    for i, tok in enumerate(tokens):
        if tok.type == "heading_open" and tok.map:
            inline = tokens[i + 1]
            headings.append((int(tok.tag[1]), inline.content.strip(), tok.map[0] + 1))
        elif tok.type in ("fence", "code_block") and tok.map:
            start, end = tok.map[0] + 1, tok.map[1]
            code_blocks.append(
                CodeBlock(language=tok.info.strip().split(" ")[0] if tok.info else "",
                          content=tok.content, line_start=start, line_end=end)
            )
            in_fence.update(range(start, end + 1))
        elif tok.type == "inline" and tok.map and tok.children:
            base_line = tok.map[0] + 1
            line_offset = 0
            pending: dict[str, str] | None = None
            text_acc = ""
            for child in tok.children:
                if child.type in ("softbreak", "hardbreak"):
                    line_offset += 1
                elif child.type == "link_open":
                    pending = {"href": str(child.attrGet("href") or "")}
                    text_acc = ""
                elif child.type == "link_close" and pending is not None:
                    links.append(Link(target=pending["href"], text=text_acc, line=base_line + line_offset))
                    pending = None
                elif child.type == "image":
                    alt = child.content or "".join(c.content for c in (child.children or []))
                    links.append(Link(target=str(child.attrGet("src") or ""), text=alt,
                                      line=base_line + line_offset, is_image=True, alt=alt or None))
                elif pending is not None and child.type in ("text", "code_inline"):
                    text_acc += child.content

    plain_lines = ["" if (n + 1) in in_fence else markdown_line_to_text(line) for n, line in enumerate(lines)]
    # code lines still count as readable text for quotes, but not as words
    readable = [line if (n + 1) in in_fence else plain_lines[n] for n, line in enumerate(lines)]

    sections: list[Section] = []
    slugs_seen: dict[str, int] = {}
    anchors: list[str] = []
    for idx, (level, text, line) in enumerate(headings):
        end = len(lines)
        for lvl2, _t, line2 in headings[idx + 1:]:
            if lvl2 <= level:
                end = line2 - 1
                break
        slug = github_slug(text)
        if slug in slugs_seen:
            slugs_seen[slug] += 1
            slug = f"{slug}-{slugs_seen[slug]}"
        else:
            slugs_seen[slug] = 0
        anchors.append(slug)
        body = "\n".join(readable[line - 1:end])
        sections.append(Section(heading=text, anchor=slug, level=level, line_start=line, line_end=end, text=body))

    title = next((t for lvl, t, _ in headings if lvl == 1), headings[0][1] if headings else rel_path)
    return Page(
        manual_id=manual_id, path=rel_path, abs_path=abs_path, format="md", title=title,
        source=source, lines=lines, plain_lines=readable, sections=sections, links=links,
        anchors=anchors, code_blocks=code_blocks, word_count=count_words(plain_lines),
    )
