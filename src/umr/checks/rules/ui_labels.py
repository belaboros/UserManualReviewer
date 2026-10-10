"""UI labels in the manuals that are not in the reference ui-strings file (spec UILABEL)."""

from __future__ import annotations

import html
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz, process, utils

from umr.checks.base import Check, CheckContext, register
from umr.checks.rules._util import Quoter, code_lines, location, max_severity
from umr.domain import Category, Finding, Journey, Page, Scope, Severity, Tier

REFERENCE_KEY = "ui_strings"
SEP = " › "
_SEP_RE = re.compile(r"\s*(?:›|&rsaquo;|&#8250;|→|->|&gt;|>)\s*")
_ACTION = re.compile(
    r"\b(?:double-click|right-click|click(?:s|ing)?|select(?:s|ing)?|press(?:es|ing)?|tap(?:s|ping)?|"
    r"choose|chooses|choosing|open(?:s|ing)?|go(?:es)?\s+to|navigate\s+to|switch\s+to)\b",
    re.I,
)
_MAX_GAP_WORDS = 3  # "click the **Save** button": at most this many words between verb and label
_CONNECTOR = re.compile(r"^\s*(?:,|and|or|and then|then|,\s*then)?\s*$", re.I)
_SENTENCE_END = re.compile(r"[.!?;:](?:\s|$)")
_MD_BOLD = re.compile(r"(\*\*|__)(?=\S)(.+?)(?<=\S)\1")
_HTML_BOLD = re.compile(r"<(strong|b)\b[^>]*>(.*?)</\1\s*>", re.I | re.S)
_TAG = re.compile(r"<[^>]+>")
_MD_MARKUP = re.compile(r"(\*\*|__|`|~~|!?\[|\]\([^)]*\))")
_SUGGEST_CUTOFF = 80.0
_SUGGEST_PATH_CUTOFF = 90.0  # paths share separators and segments, so they score high easily
_CLOSE_CUTOFF = 55.0


def normalise_label(label: str) -> str:
    text = html.unescape(_TAG.sub("", label))
    parts = [p.strip() for p in _SEP_RE.split(text)]
    return SEP.join(p for p in parts if p)


def load_labels(path: Path) -> list[str]:
    """All string leaves of the ui-strings JSON; keys starting with '_' are comments and are skipped."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out: list[str] = []

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if not str(key).startswith("_"):
                    walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)
        elif isinstance(node, str) and node.strip():
            out.append(normalise_label(node))

    walk(data)
    return out


@dataclass
class UiRef:
    label: str  # normalised, menu paths joined with " › "
    line: int
    markup: str  # verbatim source text of the reference


def _plain(prefix: str, fmt: str) -> str:
    if fmt == "md":
        return _MD_MARKUP.sub("", prefix)
    return html.unescape(_TAG.sub(" ", prefix))


def _is_action_target(before: str) -> bool:
    """True if the sentence text before a bold label ends with an action verb and at most a few words."""
    sentence = _SENTENCE_END.split(before)[-1]
    verbs = list(_ACTION.finditer(sentence))
    if not verbs:
        return False
    gap = sentence[verbs[-1].end():]
    return len(re.findall(r"[\w'’-]+", gap)) <= _MAX_GAP_WORDS


def find_ui_refs(page: Page) -> list[UiRef]:
    """Bold labels after an action verb, and bold menu paths, with their source line."""
    bold = _MD_BOLD if page.format == "md" else _HTML_BOLD
    skip = code_lines(page)
    refs: list[UiRef] = []
    for n, raw in enumerate(page.lines, 1):
        if n in skip:
            continue
        matches = list(bold.finditer(raw))
        i = 0
        prev_end, prev_was_ui = 0, False
        while i < len(matches):
            m = matches[i]
            # merge "**A** › **B** › **C**" into one menu path
            j, end = i, m.end()
            while j + 1 < len(matches) and _SEP_RE.fullmatch(raw[matches[j].end():matches[j + 1].start()]):
                j += 1
                end = matches[j].end()
            parts = [_plain(x.group(2), page.format) for x in matches[i:j + 1]]
            label = normalise_label(SEP.join(parts))
            is_path = SEP in label
            between = _plain(raw[prev_end:m.start()], page.format)
            is_ui = (is_path or _is_action_target(_plain(raw[:m.start()], page.format))
                     or (prev_was_ui and bool(_CONNECTOR.match(between))))
            if is_ui and label and not label.isdigit():
                refs.append(UiRef(label=label, line=n, markup=raw[m.start():end]))
            prev_end, prev_was_ui = end, is_ui
            i = j + 1
    return refs


@register
class UiLabelsCheck(Check):
    id = "ui-labels"
    title = "UI labels"
    description = ("Buttons, menus and menu paths named in the manuals (bold text after click, select, "
                   "open, go to, ...) that do not exist in the journey's reference ui-strings file. Runs only "
                   "when journey.yaml names a 'ui_strings' reference.")
    tier = Tier.RULE
    scope = Scope.PAGE
    categories = (Category.UI_LABEL,)

    def applies_to(self, journey: Journey) -> bool:
        return REFERENCE_KEY in journey.reference

    def run(self, ctx: CheckContext) -> list[Finding]:
        ref_path = ctx.journey.reference.get(REFERENCE_KEY)
        if ref_path is None:
            return []
        try:
            labels = load_labels(ref_path)
        except (OSError, json.JSONDecodeError) as e:
            raise ValueError(f"Cannot read UI strings reference {ref_path}: {e}") from e
        known = set(labels)
        lower = {lbl.lower(): lbl for lbl in labels}
        segments = {seg for lbl in labels for seg in lbl.split(SEP)}
        findings: list[Finding] = []
        for page in ctx.journey.pages:
            quoter = Quoter(page)
            by_line: dict[int, list[tuple[UiRef, Severity, str, str]]] = defaultdict(list)
            for ref in find_ui_refs(page):
                if ref.label in known:
                    continue
                severity, problem, fix = self._judge(ref.label, labels, lower, segments)
                by_line[ref.line].append((ref, severity, problem, fix))
            for line, items in sorted(by_line.items()):
                findings.append(self._finding(page, quoter, line, items))
        return findings

    @staticmethod
    def _judge(label: str, labels: list[str], lower: dict[str, str],
               segments: set[str]) -> tuple[Severity, str, str]:
        kind = "menu path" if SEP in label else "UI label"
        if label.lower() in lower:
            right = lower[label.lower()]
            return (Severity.MINOR, f"The {kind} '{label}' differs only in capitalisation from '{right}'.",
                    f"Did you mean '{right}'? Use the exact capitalisation shown in the application.")
        problem = f"The {kind} '{label}' does not appear in the application's UI strings."
        if SEP in label:
            unknown = [s for s in label.split(SEP) if s not in segments]
            if unknown:
                problem += " Unknown menu entries: " + ", ".join(f"'{s}'" for s in unknown) + "."
            else:
                problem += " Each entry exists, but not as this path."
        # suggest paths for a path and labels for a label
        choices = [lbl for lbl in labels if (SEP in lbl) == (SEP in label)] or labels
        best = process.extract(label, choices, scorer=fuzz.WRatio, processor=utils.default_process,
                               limit=2, score_cutoff=_CLOSE_CUTOFF)
        cutoff = _SUGGEST_PATH_CUTOFF if SEP in label else _SUGGEST_CUTOFF
        if best and best[0][1] >= cutoff:
            fix = f"Did you mean '{best[0][0]}'? Use the label exactly as it appears in the application."
        elif best:
            names = " or ".join(f"'{b[0]}'" for b in best)
            fix = (f"Closest labels in the application: {names}. Use the label exactly as it appears in the "
                   f"application, or update the UI strings reference if the label is new.")
        else:
            fix = ("Use the label exactly as it appears in the application, or update the UI strings "
                   "reference if the label is new.")
        return Severity.MAJOR, problem, fix

    @staticmethod
    def _finding(page: Page, quoter: Quoter, line: int,
                 items: list[tuple[UiRef, Severity, str, str]]) -> Finding:
        names = ", ".join(f"'{ref.label}'" for ref, *_ in items)
        title = (f"UI label {names} not found in the application" if len(items) == 1
                 else f"UI labels {names} not found in the application")
        quote = quoter.quote(line, [items[0][0].markup])
        return Finding(
            check_id=UiLabelsCheck.id, category=Category.UI_LABEL,
            severity=max_severity(sev for _, sev, _, _ in items), title=title,
            explanation=" ".join(p for _, _, p, _ in items)
            + " Readers will look for a button or menu that they cannot find.",
            suggested_fix=" ".join(f for *_, f in items), source="rule", confidence=1.0,
            locations=[location(page, line, quote)],
        )
