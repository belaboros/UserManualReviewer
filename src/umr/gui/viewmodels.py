"""Qt-free view-model helpers for the GUI (spec GUI-desktop-app).

Everything here is plain Python so it can be tested without widgets; the views only lay out what these
functions compute.
"""

from __future__ import annotations

import html
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from umr.domain import SEVERITY_ORDER, Category, Finding, Journey, Location, Page, ReviewRun, Severity, Tier

# ---------- colours ----------

BAND_GREEN = "#2e9d5b"
BAND_AMBER = "#d08a00"
BAND_RED = "#d64545"

SEVERITY_COLORS: dict[Severity, str] = {
    Severity.CRITICAL: "#c62828",
    Severity.MAJOR: "#e07020",
    Severity.MINOR: "#c9a000",
    Severity.INFO: "#4f86b8",
}

# Severities from most to least severe, for display.
SEVERITIES_DESC = list(reversed(SEVERITY_ORDER))
SEVERITY_RANK = {s: i for i, s in enumerate(SEVERITY_ORDER)}  # info 0 … critical 3

NO_FINDINGS = "No findings — 100%"
OPEN_JOURNEY = "Open a journey to start"
NO_MATCH = "No findings match the filters"
NO_RUN_DASHBOARD = "Run a review or open a saved run to see the dashboard."
NO_EVALS = "No evaluations yet — run one in Evaluate."
NONE_A = "None — rule checks only"
NONE_B = "None — no comparison"


def score_band(value: float) -> str:
    """Colour for a quality score: ≥90 green, ≥70 amber, else red (spec GUI, Dashboard)."""
    if value >= 90:
        return BAND_GREEN
    if value >= 70:
        return BAND_AMBER
    return BAND_RED


def band_name(value: float) -> str:
    return "good" if value >= 90 else "fair" if value >= 70 else "poor"


def fmt_score(value: float | None) -> str:
    return "–" if value is None else f"{value:.1f}"


def fmt_pct(value: float | None) -> str:
    return "–" if value is None else f"{value * 100:.0f}%"


def fmt_cost(value: float | None) -> str:
    if value is None:
        return "–"
    if value == 0:
        return "$0"
    return f"${value:.3g}" if value < 1 else f"${value:,.2f}"


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "–"
    if seconds < 60:
        return f"{seconds:.1f} s"
    m, s = divmod(int(round(seconds)), 60)
    return f"{m} min {s:02d} s"


def fmt_int(n: int | None) -> str:
    return "–" if n is None else f"{n:,}"


# ---------- runs ----------


def run_duration(run: ReviewRun) -> float | None:
    if run.finished_at is None:
        return None
    return (run.finished_at - run.started_at).total_seconds()


def set_score(run: ReviewRun) -> float | None:
    s = run.score_for("set")
    return s.value if s else None


def run_facts(run: ReviewRun) -> list[tuple[str, str]]:
    u = run.usage
    return [
        ("Journey", run.journey_name),
        ("Model", run.model or "none (rule checks only)"),
        ("Checks", str(len(run.checks))),
        ("Started", run.started_at.astimezone().strftime("%Y-%m-%d %H:%M:%S")),
        ("Duration", fmt_duration(run_duration(run))),
        ("Tokens", f"{fmt_int(u.input_tokens)} in · {fmt_int(u.output_tokens)} out · "
                   f"{fmt_int(u.cached_tokens)} cached"),
        ("Cost", fmt_cost(u.cost_usd)),
        ("Findings", f"{len(run.findings)} ({sum(1 for f in run.findings if f.verified)} verified)"),
    ]


@dataclass
class ManualCard:
    manual_id: str
    title: str
    score: float | None
    finding_count: int
    word_count: int


def manual_cards(run: ReviewRun, journey: Journey | None = None) -> list[ManualCard]:
    titles = {m.id: m.title for m in journey.manuals} if journey else {}
    cards = []
    for s in run.scores:
        if s.level.value == "manual":
            cards.append(ManualCard(s.target, titles.get(s.target, s.target), s.value, s.finding_count,
                                    s.word_count))
    return cards


def severity_counts(findings: list[Finding]) -> list[tuple[Severity, int, int]]:
    """(severity, verified count, unverified count), most severe first."""
    ver = Counter(f.severity for f in findings if f.verified)
    unv = Counter(f.severity for f in findings if not f.verified)
    return [(s, ver[s], unv[s]) for s in SEVERITIES_DESC]


@dataclass
class Heatmap:
    rows: list[str]  # page ids
    cols: list[str]  # category values
    counts: list[list[int]]

    @property
    def max(self) -> int:
        return max((c for row in self.counts for c in row), default=0)


def heatmap(run: ReviewRun, journey: Journey | None = None) -> Heatmap:
    """Pages × categories, counting verified findings with a location on the page."""
    findings = [f for f in run.findings if f.verified and f.locations]
    cats = [c.value for c in Category if any(f.category == c for f in findings)]
    if journey is not None:
        pages = [p.page_id for p in journey.pages]
    else:
        pages = [s.target for s in run.scores if s.level.value == "page"]
    seen = set(pages)
    for f in findings:
        for loc in f.locations:
            if loc.page_id not in seen:
                seen.add(loc.page_id)
                pages.append(loc.page_id)
    counts = [[0] * len(cats) for _ in pages]
    pidx = {p: i for i, p in enumerate(pages)}
    cidx = {c: i for i, c in enumerate(cats)}
    for f in findings:
        for pid in {loc.page_id for loc in f.locations}:
            counts[pidx[pid]][cidx[f.category.value]] += 1
    return Heatmap(pages, cats, counts)


# ---------- findings table ----------

FINDING_COLUMNS = ["Id", "Severity", "Category", "Title", "Manual(s)", "Page(s)", "Source", "Verified"]


def finding_manuals(f: Finding) -> str:
    return ", ".join(dict.fromkeys(loc.manual_id for loc in f.locations)) or "(journey)"


def finding_pages(f: Finding) -> str:
    parts = []
    for loc in f.locations:
        lines = ""
        if loc.line_start is not None:
            end = loc.line_end or loc.line_start
            lines = f":{loc.line_start}" if end == loc.line_start else f":{loc.line_start}-{end}"
        parts.append(f"{loc.page_path}{lines}")
    return ", ".join(dict.fromkeys(parts)) or "–"


def finding_row(f: Finding) -> list[str]:
    return [f.id, f.severity.value, f.category.value, f.title, finding_manuals(f), finding_pages(f), f.source,
            "✓ verified" if f.verified else "unverified"]


def finding_sort_key(f: Finding, column: int) -> Any:
    if column == 1:
        return SEVERITY_RANK[f.severity]
    if column == 7:
        return int(f.verified)
    return finding_row(f)[column].lower()


@dataclass
class FindingFilter:
    severity: Severity | None = None
    category: Category | None = None
    manual: str | None = None
    verified_only: bool = False
    text: str = ""

    def accepts(self, f: Finding) -> bool:
        if self.severity is not None and f.severity != self.severity:
            return False
        if self.category is not None and f.category != self.category:
            return False
        if self.manual and not any(loc.manual_id == self.manual for loc in f.locations):
            return False
        if self.verified_only and not f.verified:
            return False
        needle = self.text.strip().lower()
        if needle:
            hay = " ".join([f.id, f.title, f.explanation, f.suggested_fix, f.check_id, f.category.value,
                            f.source, *(loc.quote for loc in f.locations),
                            *(loc.page_id for loc in f.locations)]).lower()
            if not all(word in hay for word in needle.split()):
                return False
        return True


# ---------- checks ----------


@dataclass
class CheckInfo:
    id: str
    title: str
    description: str
    tier: Tier
    categories: list[str] = field(default_factory=list)

    @property
    def needs_llm(self) -> bool:
        return self.tier == Tier.LLM


def check_infos(classes: list[Any]) -> list[CheckInfo]:
    return [CheckInfo(c.id, getattr(c, "title", c.id), getattr(c, "description", ""), Tier(c.tier),
                      [str(getattr(x, "value", x)) for x in getattr(c, "categories", ())]) for c in classes]


def group_checks(checks: list[CheckInfo]) -> list[tuple[Tier, list[CheckInfo]]]:
    return [(t, [c for c in checks if c.tier == t]) for t in (Tier.RULE, Tier.LLM)
            if any(c.tier == t for c in checks)]


def selection_summary(checks: list[CheckInfo], selected: set[str], has_model: bool) -> str:
    chosen = [c for c in checks if c.id in selected]
    llm = sum(1 for c in chosen if c.needs_llm)
    text = f"{len(chosen)} of {len(checks)} checks selected · {llm} need an LLM"
    if llm and not has_model:
        text += " — no model A chosen, LLM checks will be skipped"
    return text


# ---------- progress log ----------


def progress_line(event: Any, label: str | None = None) -> str | None:
    """One log line for a ProgressEvent (or None to skip)."""
    prefix = f"[{label}] " if label else ""
    kind = getattr(event, "kind", "")
    if kind == "started":
        return f"{prefix}Review started: {event.total} checks"
    if kind == "check_started":
        return f"{prefix}▶ {event.check_id} started"
    if kind == "check_finished":
        res = event.result
        if res is not None and res.error:
            return f"{prefix}✗ {event.check_id} failed: {res.error}  ({event.done}/{event.total})"
        n = len(res.findings) if res is not None else 0
        dur = f", {res.duration_s:.2f} s" if res is not None else ""
        return f"{prefix}✓ {event.check_id} finished: {n} finding{'s' if n != 1 else ''}{dur}  " \
               f"({event.done}/{event.total})"
    if kind == "finished":
        return f"{prefix}Review finished"
    msg = getattr(event, "message", "")
    return f"{prefix}{msg}" if msg else None


def progress_percent(event: Any) -> int | None:
    total = getattr(event, "total", 0)
    if not total:
        return None
    return int(round(100 * getattr(event, "done", 0) / total))


# ---------- errors ----------


def friendly_error(exc: BaseException) -> tuple[str, str]:
    """(dialog title, message) for an exception."""
    name = type(exc).__name__
    msg = str(exc) or name
    if name == "LlmError":
        hint = ""
        if re.search(r"api[ _-]?key|environment variable|unauthori[sz]ed|401", msg, re.I):
            hint = ("\n\nSet the environment variable named in config/llm-providers.yaml (api_key_env) "
                    "or put it in a .env file, then start the review again.")
        return "Model error", msg + hint
    if name == "IngestError":
        return "Could not open the journey", msg
    if isinstance(exc, FileNotFoundError):
        return "File not found", msg
    if isinstance(exc, ValueError | KeyError):
        return "Invalid input", msg
    return "Something went wrong", f"{name}: {msg}"


# ---------- passages ----------

CONTEXT_LINES = 5


def _page_line_texts(page: Page) -> list[str]:
    if page.format == "html":
        return [p if p.strip() else "" for p in page.plain_lines]
    return list(page.lines)


def _mark_quote(line: str, quote: str, mark_style: str) -> str:
    """Escape `line` and wrap the part matching `quote` (or a long fragment of it)."""
    q = " ".join(quote.split())
    if q:
        idx = line.lower().find(q.lower())
        if idx < 0:
            # quote spanning several lines: mark the longest quote fragment present on this line
            words = q.split()
            for n in range(len(words), 2, -1):
                for i in range(len(words) - n + 1):
                    frag = " ".join(words[i:i + n])
                    idx = line.lower().find(frag.lower())
                    if idx >= 0:
                        q = frag
                        break
                if idx >= 0:
                    break
        if idx >= 0:
            return (html.escape(line[:idx]) + f'<span style="{mark_style}">'
                    + html.escape(line[idx:idx + len(q)]) + "</span>" + html.escape(line[idx + len(q):]))
    return html.escape(line)


@dataclass
class PassageColors:
    text: str = "#1f1f1f"
    muted: str = "#777777"
    highlight_bg: str = "#fff2a8"
    mark_bg: str = "#ffd54f"
    mark_fg: str = "#000000"
    border: str = "#cccccc"
    code_bg: str = "#f6f6f6"


def passage_html(journey: Journey | None, loc: Location, colors: PassageColors | None = None,
                 context: int = CONTEXT_LINES) -> str:
    """One location as an HTML table of numbered lines with the located lines highlighted."""
    c = colors or PassageColors()
    title = html.escape(loc.page_id)
    lines_label = ""
    if loc.line_start is not None:
        end = loc.line_end or loc.line_start
        lines_label = f" · line {loc.line_start}" if end == loc.line_start else f" · lines {loc.line_start}–{end}"
    status = "" if loc.verified else f' <span style="color:{BAND_RED}">· unverified</span>'
    head = f'<p style="margin:0 0 4px 0"><b>{title}</b><span style="color:{c.muted}">{lines_label}</span>' \
           f"{status}</p>"
    page = journey.page(loc.page_id) if journey else None
    if page is None or loc.line_start is None:
        why = "source not available" if page is None else "passage not found in the source"
        quote = html.escape(loc.quote) if loc.quote else "(no quote)"
        return head + f'<p style="color:{c.muted}"><i>{why}</i></p>' \
                      f'<p style="background:{c.highlight_bg}; color:{c.text}; padding:4px">“{quote}”</p>'
    texts = _page_line_texts(page)
    start, end = loc.line_start, loc.line_end or loc.line_start
    lo, hi = max(1, start - context), min(len(texts), end + context)
    mark = f"background-color:{c.mark_bg}; color:{c.mark_fg}; font-weight:bold"
    rows = []
    for n in range(lo, hi + 1):
        line = texts[n - 1].rstrip("\n")
        hit = start <= n <= end
        body = _mark_quote(line, loc.quote, mark) if hit else html.escape(line)
        bg = f' bgcolor="{c.highlight_bg}"' if hit else ""
        rows.append(f'<tr{bg}><td align="right" style="color:{c.muted}; padding-right:6px">{n}</td>'
                    f'<td style="color:{c.text}; white-space:pre-wrap">{body or "&nbsp;"}</td></tr>')
    table = (f'<table cellspacing="0" cellpadding="1" width="100%" style="font-family:monospace; '
             f'border:1px solid {c.border}">' + "".join(rows) + "</table>")
    return head + table


def finding_html(f: Finding, journey: Journey | None, colors: PassageColors | None = None,
                 extra: str = "") -> str:
    c = colors or PassageColors()
    sev = SEVERITY_COLORS[f.severity]
    unv = "" if f.verified else f' · <span style="color:{BAND_RED}"><b>unverified</b></span>'
    parts = [
        f'<h2 style="margin-bottom:2px">{html.escape(f.title)}</h2>',
        f'<p style="color:{c.muted}; margin-top:0"><span style="color:{sev}"><b>{f.severity.value}</b></span>'
        f" · {html.escape(f.category.value)} · check <code>{html.escape(f.check_id)}</code>"
        f" · {html.escape(f.source)} · {html.escape(f.id)}{unv}</p>",
    ]
    if extra:
        parts.append(extra)
    if f.explanation:
        parts.append(f"<h4>Explanation</h4><p>{html.escape(f.explanation)}</p>")
    if f.suggested_fix:
        parts.append(f"<h4>Suggested fix</h4><p>{html.escape(f.suggested_fix)}</p>")
    if f.locations:
        parts.append(f"<h4>Source passage{'s' if len(f.locations) > 1 else ''}</h4>")
        cells = [passage_html(journey, loc, c) for loc in f.locations]
        rows = []
        for i in range(0, len(cells), 2):
            pair = cells[i:i + 2]
            width = "50%" if len(cells) > 1 else "100%"
            tds = "".join(f'<td valign="top" width="{width}" style="padding:4px">{x}</td>' for x in pair)
            rows.append(f"<tr>{tds}</tr>")
        parts.append('<table width="100%" cellspacing="4">' + "".join(rows) + "</table>")
    else:
        parts.append(f'<p style="color:{c.muted}"><i>Journey-level finding without a location.</i></p>')
    return "".join(parts)


def finding_label(f: Finding) -> str:
    marker = "" if f.verified else "  (unverified)"
    return f"[{f.severity.value}] {f.category.value} — {f.title}{marker}"


# ---------- compare ----------


def compare_rows(comparison: Any) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Header labels and (metric, A, B) rows for the comparison summary."""
    a, b = comparison.run_a, comparison.run_b
    la, lb = a.model or "rules", b.model or "rules"
    rows: list[tuple[str, str, str]] = [("Model", la, lb)]
    rows.append(("Set score", fmt_score(set_score(a)), fmt_score(set_score(b))))
    rows.append(("Findings", str(len(a.findings)), str(len(b.findings))))
    rows.append(("Verified findings", str(sum(f.verified for f in a.findings)),
                 str(sum(f.verified for f in b.findings))))
    rows.append(("Tokens (in / out)", f"{fmt_int(a.usage.input_tokens)} / {fmt_int(a.usage.output_tokens)}",
                 f"{fmt_int(b.usage.input_tokens)} / {fmt_int(b.usage.output_tokens)}"))
    rows.append(("Cost", fmt_cost(a.usage.cost_usd), fmt_cost(b.usage.cost_usd)))
    rows.append(("Duration", fmt_duration(run_duration(a)), fmt_duration(run_duration(b))))
    return [la, lb], rows


# ---------- evaluation ----------

METRIC_LABELS = [
    ("recall", "Recall"),
    ("precision", "Precision"),
    ("f1", "F1"),
    ("category_accuracy", "Category accuracy"),
    ("severity_accuracy", "Severity accuracy"),
    ("verified_quote_rate", "Verified quotes"),
    ("valid_output_rate", "Valid output"),
    ("stability", "Stability"),
]


def metric_rows(metrics: Any) -> list[tuple[str, float | None]]:
    out = []
    for key, label in METRIC_LABELS:
        v = getattr(metrics, key, None)
        out.append((label, float(v) if v is not None else None))
    return out


def _attr(obj: Any, *names: str, default: Any = None) -> Any:
    for n in names:
        if isinstance(obj, dict) and n in obj:
            return obj[n]
        if hasattr(obj, n):
            return getattr(obj, n)
    return default


def expected_label(e: Any) -> str:
    locs = _attr(e, "locations", default=[]) or []
    pages = []
    for loc in locs:
        page = _attr(loc, "page", "page_path", "page_id", default="")
        if page:
            pages.append(str(page))
    where = f"  ({', '.join(dict.fromkeys(pages))})" if pages else ""
    sev = _attr(e, "severity", default="")
    cat = _attr(e, "category", default="")
    title = _attr(e, "title", default="") or ""
    return f"{_attr(e, 'id', default='')} [{getattr(sev, 'value', sev)}] {getattr(cat, 'value', cat)} — " \
           f"{title}{where}"


LEADERBOARD_COLUMNS = ["Rank", "Model", "Benchmark", "Key version", "Eval score", "Recall", "Precision", "F1",
                       "Verified quotes", "Valid output", "Cost", "Duration", "Date"]


def leaderboard_row(rank: int, r: Any) -> list[tuple[str, Any]]:
    """(display text, sort value) per leaderboard column."""
    m = r.metrics
    usage = getattr(r, "usage", None)
    cost = getattr(usage, "cost_usd", None) if usage is not None else None
    started = getattr(r, "started_at", None)
    date = started.astimezone().strftime("%Y-%m-%d %H:%M") if started is not None else "–"
    vals: list[tuple[str, Any]] = [
        (str(rank), rank),
        (str(r.model), str(r.model).lower()),
        (str(r.benchmark), str(r.benchmark).lower()),
        (str(getattr(r, "key_version", "–")), str(getattr(r, "key_version", ""))),
        (fmt_score(r.eval_score), float(r.eval_score)),
    ]
    for key in ("recall", "precision", "f1", "verified_quote_rate", "valid_output_rate"):
        v = getattr(m, key, None)
        vals.append((fmt_pct(v), float(v) if v is not None else -1.0))
    vals.append((fmt_cost(cost), float(cost) if cost is not None else -1.0))
    dur = getattr(r, "duration_s", None)
    vals.append((fmt_duration(dur), float(dur) if dur is not None else -1.0))
    vals.append((date, started.timestamp() if started is not None else 0.0))
    return vals
