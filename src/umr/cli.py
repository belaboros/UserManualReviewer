"""Command-line interface: `umr review | compare | eval | checks | providers | gui`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from umr.app import ProgressEvent, ReviewService
from umr.checks import CheckRegistry
from umr.domain import SEVERITY_ORDER, ReviewRun, Scope
from umr.ingest import IngestError, load_journey
from umr.scoring import ScoringConfig
from umr.storage import RunStore

DEFAULT_PROVIDERS = Path("config/llm-providers.yaml")
EXAMPLE_PROVIDERS = Path("config/llm-providers.example.yaml")


def _providers_path(arg: str | None) -> Path:
    if arg:
        return Path(arg)
    return DEFAULT_PROVIDERS if DEFAULT_PROVIDERS.exists() else EXAMPLE_PROVIDERS


def _provider(name: str | None, providers_file: str | None):  # type: ignore[no-untyped-def]
    if not name:
        return None
    from umr.llm.config import load_providers, make_provider

    configs = {c.name: c for c in load_providers(_providers_path(providers_file))}
    if name not in configs:
        raise SystemExit(f"Unknown model '{name}'. Configured: {', '.join(configs) or 'none'}")
    return make_provider(configs[name])


def _progress(event: ProgressEvent) -> None:
    if event.kind == "check_finished" and event.result:
        r = event.result
        status = f"ERROR {r.error}" if r.error else f"{len(r.findings)} findings"
        print(f"  [{event.done}/{event.total}] {r.check_id:<16} {status}  ({r.duration_s:.1f}s)", file=sys.stderr)


def print_run(run: ReviewRun) -> None:
    s = run.score_for("set")
    print(f"\n{run.journey_name}  ·  model: {run.model or 'rules only'}")
    if s:
        print(f"Quality score (set): {s.value:.1f}%   findings: {len(run.findings)}")
    for score in run.scores:
        if score.level == Scope.MANUAL:
            print(f"  {score.target:<24} {score.value:5.1f}%  ({score.finding_count} findings)")
    print()
    order = {sev: i for i, sev in enumerate(reversed(SEVERITY_ORDER))}
    for f in sorted(run.findings, key=lambda f: (order[f.severity], f.category)):
        locs = ", ".join(f"{loc.page_id}:{loc.line_start or '?'}" for loc in f.locations) or "journey"
        mark = "" if f.verified else "  [unverified]"
        print(f"{f.id}  {f.severity:<8} {f.category:<18} {f.title}{mark}\n       {locs}")
    if run.usage.calls:
        u = run.usage
        print(f"\nLLM: {u.calls} calls, {u.input_tokens} in / {u.output_tokens} out tokens "
              f"({u.cached_tokens} cached), ~${u.cost_usd:.3f}")
    for e in run.errors:
        print(f"Check failed: {e.check_id}: {e.message}", file=sys.stderr)
    if run.errors and u.calls:
        from umr.llm.calllog import log_file

        print(f"LLM requests and responses: {log_file()}", file=sys.stderr)


def cmd_review(args: argparse.Namespace) -> int:
    journey = load_journey(Path(args.journey))
    provider = _provider(args.model, args.providers)
    checks = args.checks.split(",") if args.checks else (["all"] if provider else ["rules"])
    service = ReviewService(ScoringConfig.load(Path(args.scoring)))
    run = service.review(journey, checks, provider, progress=_progress, journey_path=Path(args.journey))
    path = RunStore().save(run)
    if args.json:
        print(run.model_dump_json(indent=2))
    else:
        print_run(run)
        print(f"\nSaved: {path}")
    return 1 if run.errors else 0


def cmd_compare(args: argparse.Namespace) -> int:
    from umr.app.compare import CompareService

    journey = load_journey(Path(args.journey))
    a, b = _provider(args.model_a, args.providers), _provider(args.model_b, args.providers)
    checks = args.checks.split(",") if args.checks else ["all"]
    service = CompareService(ReviewService(ScoringConfig.load(Path(args.scoring))))
    cmp = service.run_and_compare(journey, checks, a, b,
                                  progress=lambda side, e: _progress(e) if e.kind == "check_finished" else None)
    store = RunStore()
    store.save(cmp.run_a)
    store.save(cmp.run_b)
    sa, sb = cmp.run_a.score_for("set"), cmp.run_b.score_for("set")
    print(f"\n{'':<22}{args.model_a:>16}{args.model_b:>16}")
    print(f"{'Quality score':<22}{(sa.value if sa else 0):>15.1f}%{(sb.value if sb else 0):>15.1f}%")
    print(f"{'Findings':<22}{len(cmp.run_a.findings):>16}{len(cmp.run_b.findings):>16}")
    print(f"{'Cost (USD)':<22}{cmp.run_a.usage.cost_usd:>16.3f}{cmp.run_b.usage.cost_usd:>16.3f}")
    print(f"\nFound by both: {len(cmp.both)}   only {args.model_a}: {len(cmp.only_a)}   "
          f"only {args.model_b}: {len(cmp.only_b)}")
    for title, items in ((f"Only {args.model_a}", cmp.only_a), (f"Only {args.model_b}", cmp.only_b)):
        print(f"\n{title}:")
        for f in items:
            print(f"  {f.severity:<8} {f.category:<18} {f.title}")
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    from umr.app.evaluation import EvalService, leaderboard
    from umr.storage.evals import EvalStore

    store = EvalStore()
    if args.leaderboard:
        rows = leaderboard(store.load_all())
        print(f"{'#':<3}{'model':<22}{'bench':<10}{'score':>7}{'recall':>8}{'prec':>7}{'F1':>7}{'cost $':>9}")
        for i, r in enumerate(rows, 1):
            m = r.metrics
            print(f"{i:<3}{r.model:<22}{r.benchmark:<10}{r.eval_score:>7.1f}{m.recall:>8.2f}{m.precision:>7.2f}"
                  f"{m.f1:>7.2f}{r.usage.cost_usd:>9.3f}")
        return 0
    if not args.model:
        raise SystemExit("--model is required (or use --leaderboard)")
    provider = _provider(args.model, args.providers)
    service = EvalService(Path(args.config))
    result = service.evaluate(provider, benchmark=args.benchmark, repeat=args.repeat,
                              include_rules=args.include_rules, progress=_progress)
    path = store.save(result)
    m = result.metrics
    print(f"\nEval score for {result.model} on {result.benchmark} (key v{result.key_version}): "
          f"{result.eval_score:.1f}/100")
    print(f"  recall {m.recall:.2f}  precision {m.precision:.2f}  F1 {m.f1:.2f}  category {m.category_accuracy:.2f}"
          f"  severity {m.severity_accuracy:.2f}")
    print(f"  verified quotes {m.verified_quote_rate:.2f}  valid output {m.valid_output_rate:.2f}"
          + (f"  stability {m.stability:.2f}" if m.stability is not None else ""))
    print(f"  cost ${result.usage.cost_usd:.3f}  time {result.duration_s:.0f}s  tokens "
          f"{result.usage.input_tokens}/{result.usage.output_tokens}")
    print("\nPer category:")
    for c in result.per_category:
        print(f"  {c.category:<20} found {c.found}/{c.expected}  recall {c.recall:.2f}  precision {c.precision:.2f}")
    print(f"\nMissed ({len(result.missed)}):")
    for e in result.missed:
        print(f"  {e.id:<5} {e.category:<18} {e.title}")
    print(f"\nUnexpected ({len(result.unexpected)}):")
    for f in result.unexpected:
        print(f"  {f.category:<18} {f.title}")
    print(f"\nSaved: {path}")
    return 0


def cmd_checks(args: argparse.Namespace) -> int:
    for c in sorted(CheckRegistry.all(), key=lambda c: (c.tier, c.id)):
        print(f"{c.id:<18} {c.tier:<5} {c.scope:<8} {c.title}")
    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    from umr.llm.config import get_api_key, load_providers

    path = _providers_path(args.providers)
    if args.test:
        return _test_provider(args.test, args.providers)
    print(f"From {path}:")
    for c in load_providers(path):
        key = "key set" if get_api_key(c) else ("no key needed" if not c.api_key_env else f"${c.api_key_env} missing")
        print(f"  {c.name:<18} {c.adapter:<18} {c.model:<26} {key}")
    return 0


def _test_provider(name: str, providers_file: str | None) -> int:
    """Send one tiny structured request, to debug a provider's URL, model and JSON mode (AC-LLM-26)."""
    from umr.llm import calllog
    from umr.llm.base import LlmError

    provider = _provider(name, providers_file)
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}, "required": ["ok"],
              "additionalProperties": False}
    try:
        result = provider.complete(system="You answer with JSON only.", cache_prefix="Connection test.",
                                   prompt='Reply with {"ok": true}.', schema=schema, schema_name="ping")
    except LlmError as e:
        print(f"FAILED: {e}\nFull request and response: {calllog.log_file()}", file=sys.stderr)
        return 3
    print(f"OK: {name} answered {result.raw_text.strip()[:200]!r} in {result.usage.duration_s:.1f} s "
          f"({result.usage.input_tokens} in / {result.usage.output_tokens} out tokens)")
    print(f"Full request and response: {calllog.log_file()}")
    return 0


def cmd_gui(args: argparse.Namespace) -> int:
    from umr.gui.app import main as gui_main

    return gui_main()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="umr", description="Review related user manuals with rule checks and LLMs.")
    p.add_argument("--providers", help="LLM provider config (default config/llm-providers.yaml)")
    p.add_argument("-v", "--verbose", action="store_true", help="print every LLM request and response summary")
    sub = p.add_subparsers(dest="command", required=True)

    r = sub.add_parser("review", help="review a journey or a manual folder")
    r.add_argument("journey", help="journey.yaml, a folder containing it, or a single manual folder")
    r.add_argument("--model", help="provider name from the config; omit for rule checks only")
    r.add_argument("--checks", help="comma-separated check ids, or all | rules | llm")
    r.add_argument("--scoring", default="config/scoring.yaml")
    r.add_argument("--json", action="store_true", help="print the run as JSON")
    r.set_defaults(func=cmd_review)

    c = sub.add_parser("compare", help="run the same review with two models side by side")
    c.add_argument("journey")
    c.add_argument("model_a")
    c.add_argument("model_b")
    c.add_argument("--checks")
    c.add_argument("--scoring", default="config/scoring.yaml")
    c.set_defaults(func=cmd_compare)

    e = sub.add_parser("eval", help="evaluate an LLM against benchmark sample manuals")
    e.add_argument("--model")
    e.add_argument("--benchmark", default="shopflow")
    e.add_argument("--repeat", type=int, default=1)
    e.add_argument("--include-rules", action="store_true")
    e.add_argument("--config", default="config/eval.yaml")
    e.add_argument("--leaderboard", action="store_true", help="show all saved evaluations ranked")
    e.set_defaults(func=cmd_eval)

    sub.add_parser("checks", help="list available checks").set_defaults(func=cmd_checks)
    pr = sub.add_parser("providers", help="list configured LLM providers")
    pr.add_argument("--test", metavar="NAME", help="send one tiny request to this provider and show the result")
    pr.set_defaults(func=cmd_providers)
    sub.add_parser("gui", help="start the desktop app").set_defaults(func=cmd_gui)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.verbose:
        import logging

        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
        llm_logger = logging.getLogger("umr.llm")
        llm_logger.addHandler(handler)
        llm_logger.setLevel(logging.INFO)
    try:
        return int(args.func(args))
    except IngestError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        from umr.llm.base import LlmError

        if isinstance(e, LlmError):
            from umr.llm.calllog import log_file

            print(f"LLM error: {e}\nFull request and response: {log_file()}", file=sys.stderr)
            return 3
        raise


if __name__ == "__main__":
    raise SystemExit(main())
