"""Parse an HTML file into a Page with source line numbers."""

from pathlib import Path

from bs4 import BeautifulSoup, Tag

from umr.domain import CodeBlock, Link, Page, Section
from umr.ingest.text import count_words, html_line_to_text

_HEADINGS = ["h1", "h2", "h3", "h4", "h5", "h6"]


def _line(tag: Tag) -> int:
    return int(tag.sourceline or 1)


def parse_html(manual_id: str, rel_path: str, abs_path: Path) -> Page:
    source = abs_path.read_text(encoding="utf-8")
    lines = source.splitlines()
    soup = BeautifulSoup(source, "html.parser")

    plain_lines = [html_line_to_text(line) for line in lines]
    # <title> and <head> are not readable body text
    head = soup.find("head")
    if isinstance(head, Tag) and head.sourceline:
        head_end = source[: source.find("</head>")].count("\n") + 1 if "</head>" in source else head.sourceline
        for n in range(head.sourceline - 1, min(head_end, len(plain_lines))):
            plain_lines[n] = ""

    anchors: list[str] = []
    for tag in soup.find_all(attrs={"id": True}):
        anchors.append(str(tag["id"]))
    for tag in soup.find_all("a", attrs={"name": True}):
        anchors.append(str(tag["name"]))

    links: list[Link] = []
    for a in soup.find_all("a", href=True):
        links.append(Link(target=str(a["href"]), text=a.get_text(" ", strip=True), line=_line(a)))
    for img in soup.find_all("img"):
        alt = img.get("alt")
        links.append(Link(target=str(img.get("src", "")), text=str(alt or ""), line=_line(img), is_image=True,
                          alt=str(alt) if alt else None))

    code_blocks: list[CodeBlock] = []
    for pre in soup.find_all("pre"):
        code = pre.find("code")
        lang = ""
        if isinstance(code, Tag):
            for cls in code.get("class") or []:
                if str(cls).startswith("language-"):
                    lang = str(cls)[9:]
        content = pre.get_text()
        start = _line(pre)
        code_blocks.append(CodeBlock(language=lang, content=content, line_start=start,
                                     line_end=start + content.count("\n")))

    heads = [h for h in soup.find_all(_HEADINGS)]
    sections: list[Section] = []
    for idx, h in enumerate(heads):
        level = int(h.name[1])
        start = _line(h)
        end = len(lines)
        for h2 in heads[idx + 1:]:
            if int(h2.name[1]) <= level:
                end = _line(h2) - 1
                break
        sections.append(Section(heading=h.get_text(" ", strip=True), anchor=str(h.get("id") or ""),
                                level=level, line_start=start, line_end=end,
                                text="\n".join(plain_lines[start - 1:end])))

    title_tag = soup.find("h1") or soup.find("title")
    title = title_tag.get_text(" ", strip=True) if title_tag else rel_path
    return Page(
        manual_id=manual_id, path=rel_path, abs_path=abs_path, format="html", title=title,
        source=source, lines=lines, plain_lines=plain_lines, sections=sections, links=links,
        anchors=anchors, code_blocks=code_blocks, word_count=count_words(plain_lines),
    )
