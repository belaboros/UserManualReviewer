"""Helpers that turn markup lines into readable text, line by line."""

import html
import re

_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_MD_MARKS = re.compile(r"(\*\*|__|`|~~)")
_MD_PREFIX = re.compile(r"^\s{0,3}(#{1,6}\s+|>\s?|[-*+]\s+|\d+[.)]\s+)")
_TAG = re.compile(r"<[^>]+>")
_WORD = re.compile(r"[\w'’-]+")


def markdown_line_to_text(line: str) -> str:
    s = _MD_LINK.sub(r"\1", line)
    s = _MD_MARKS.sub("", s)
    s = _MD_PREFIX.sub("", s)
    if s.strip().startswith("|"):
        cells = [c.strip() for c in s.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
            return ""
        s = "  ".join(c for c in cells if c)
    return s.rstrip()


def html_line_to_text(line: str) -> str:
    s = _TAG.sub(" ", line)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def count_words(lines: list[str]) -> int:
    return sum(len(_WORD.findall(line)) for line in lines)
