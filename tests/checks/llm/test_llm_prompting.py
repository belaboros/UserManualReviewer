"""Spec PROMPT: corpus rendering, prompt layout, response mapping, context budget."""

from umr.app.review import ReviewService
from umr.checks import CheckContext
from umr.checks.llm.consistency import ConsistencyCheck
from umr.checks.llm.contradictions import ContradictionsCheck
from umr.checks.llm.journey import JourneyCheck
from umr.checks.llm.llm_check import PromptUnit
from umr.checks.llm.procedures import ProceduresCheck
from umr.checks.llm.prompting import (
    SYSTEM_PROMPT,
    FindingsResponse,
    map_category,
    render_corpus,
    split_page_id,
    to_findings,
)
from umr.checks.llm.terminology import TerminologyCheck
from umr.domain import Category, Severity
from umr.llm import Adapter, ProviderConfig
from umr.llm.fake import FakeProvider

ALL = [ContradictionsCheck, ConsistencyCheck, JourneyCheck, TerminologyCheck, ProceduresCheck]


def finding(category="contradiction", page="orders/create.md", quote="can be cancelled", **kw):
    f = {"category": category, "severity": "major", "title": "T", "explanation": "E", "suggested_fix": "F",
         "confidence": 0.9, "locations": [{"page": page, "quote": quote}]}
    f.update(kw)
    return f


def small_provider(responses=None, context_tokens=128_000) -> FakeProvider:
    cfg = ProviderConfig(name="fake", adapter=Adapter.FAKE, model="fake-model", context_tokens=context_tokens)
    return FakeProvider(responses, config=cfg)


def test_AC_PROMPT_01_corpus_is_deterministic_with_page_headers(journey):
    a = render_corpus(journey)
    assert a == render_corpus(journey)
    assert a.startswith("JOURNEY: Test journey\nDESCRIPTION: Order from capture to delivery.\nMANUALS:\n")
    for page in journey.pages:
        assert f"=== PAGE {page.page_id} (manual: " in a
    assert "=== PAGE orders/create.md (manual: Orders Manual, version 1.0) ===" in a
    assert a.index("=== PAGE orders/") < a.index("=== PAGE delivery/")


def test_AC_PROMPT_02_body_is_readable_text_with_empty_runs_collapsed(journey):
    text = render_corpus(journey)
    assert "**" not in text and "](create.md)" not in text
    assert "1. Open the Orders dashboard." in text and "2. Click New Order." in text
    assert "This manual explains how to capture orders.\n\nSee Creating." in text


def test_AC_PROMPT_03_reference_files_included(journey, single_manual):
    text = render_corpus(journey)
    assert "=== REFERENCE ui_strings: ui.json" in text and '"order.new": "New Order"' in text
    assert text.index("=== REFERENCE") < text.index("=== PAGE")
    assert "REFERENCE" not in render_corpus(single_manual)


def test_AC_PROMPT_03_subset_rendering(journey):
    orders = journey.manual("orders")
    assert orders is not None
    text = render_corpus(journey, manuals=[orders])
    assert "=== PAGE orders/" in text and "=== PAGE delivery/" not in text
    one = render_corpus(journey, pages=[orders.pages[0]])
    assert one.count("=== PAGE ") == 1


def test_AC_PROMPT_04_corpus_first_identical_across_journey_checks(journey):
    fake = FakeProvider()
    for cls in (ContradictionsCheck, JourneyCheck, TerminologyCheck):
        cls().run(CheckContext(journey=journey, provider=fake))
    prefixes = {c["cache_prefix"] for c in fake.calls}
    systems = {c["system"] for c in fake.calls}
    assert prefixes == {render_corpus(journey)} and systems == {SYSTEM_PROMPT}
    prompts = [c["prompt"] for c in fake.calls]
    assert len(set(prompts)) == 3 and all(p.startswith("TASK\n") for p in prompts)
    assert all("=== PAGE" not in p for p in prompts)


def test_AC_PROMPT_04_system_prompt_requires_verbatim_quotes():
    s = SYSTEM_PROMPT.lower()
    assert "5 to 25" in s and "exactly" in s and "never paraphrase" in s
    assert '{"findings": []}' in SYSTEM_PROMPT and "page header" in s


def test_AC_PROMPT_05_json_mapped_to_findings(journey):
    resp = FindingsResponse.model_validate({"findings": [finding(locations=[
        {"page": "orders/create.md", "quote": "can be cancelled"},
        {"page": "delivery/statuses.md", "quote": "can no longer be cancelled"}])]})
    [f] = to_findings(resp, check_id="contradictions", categories=ContradictionsCheck.categories,
                      source="claude", journey=journey)
    assert f.check_id == "contradictions" and f.source == "claude" and f.category == Category.CONTRADICTION
    assert f.severity == Severity.MAJOR and f.confidence == 0.9 and f.suggested_fix == "F"
    assert [(loc.manual_id, loc.page_path, loc.quote) for loc in f.locations] == [
        ("orders", "create.md", "can be cancelled"), ("delivery", "statuses.md", "can no longer be cancelled")]


def test_AC_PROMPT_05_page_id_variants(journey):
    assert split_page_id(journey, "=== PAGE orders/create.md (manual: X)") == ("orders", "create.md")
    assert split_page_id(journey, "`delivery/statuses.md`") == ("delivery", "statuses.md")
    assert split_page_id(journey, "other/a/b.md") == ("other", "a/b.md")
    assert split_page_id(journey, "create.md") == ("", "create.md")


def test_AC_PROMPT_06_unknown_category_maps_to_primary_and_severity_synonyms(journey):
    allowed = ConsistencyCheck.categories
    assert map_category("banana", allowed) == Category.INCONSISTENCY
    assert map_category("VALUE_CONFLICT", allowed) == Category.VALUE_CONFLICT
    assert map_category("stale version", allowed) == Category.STALE_VERSION
    assert map_category("contradiction", allowed) == Category.INCONSISTENCY  # not allowed for this check
    resp = FindingsResponse.model_validate({"findings": [finding(severity="High", confidence=85)]})
    assert resp.findings[0].severity == "major" and resp.findings[0].confidence == 0.85
    resp = FindingsResponse.model_validate({"findings": [finding(severity="whatever", explanation=None)]})
    assert resp.findings[0].severity == "minor" and resp.findings[0].explanation == ""


def test_AC_PROMPT_07_findings_without_location_dropped(journey):
    fake = FakeProvider(lambda s, p, q: {"findings": [finding("journey-gap", locations=[]),
                                                      finding("journey-gap")]})
    found = JourneyCheck().run(CheckContext(journey=journey, provider=fake))
    assert len(found) == 1


def test_AC_PROMPT_08_journey_check_over_budget_runs_per_manual_pair(make_journey):
    filler = "Operators follow the documented procedure for every order. " * 60
    big = make_journey({mid: {"index.md": f"# {mid}\n\n{filler}\n"} for mid in ("orders", "delivery", "notify")})
    check = JourneyCheck()

    def tokens(manuals):
        unit = PromptUnit(manuals)
        return (len(SYSTEM_PROMPT) + len(unit.corpus(big)) + len(check.instruction(unit))) // 4

    full, pair = tokens(big.manuals), tokens(big.manuals[:2]) + 100
    assert pair < full
    fake = small_provider(context_tokens=int((full + pair) / 2 / 0.7))  # full set does not fit, pairs do
    pairs: list[list[str]] = []

    def respond(system, prefix, prompt):
        ids = sorted({line[len("=== PAGE "):].split("/")[0] for line in prefix.splitlines()
                      if line.startswith("=== PAGE")})
        pairs.append(ids)
        return {"findings": [finding("journey-gap", page=f"{ids[0]}/index.md", quote="x")]}

    fake.responses = respond
    found = check.run(CheckContext(journey=big, provider=fake))
    assert sorted(pairs) == [["delivery", "notify"], ["delivery", "orders"], ["notify", "orders"]]
    assert all("you see only" in c["prompt"] for c in fake.calls)
    # merged; the same finding reported for delivery/index.md by two pairs is de-duplicated
    assert sorted(f.locations[0].manual_id for f in found) == ["delivery", "notify"]


def test_AC_PROMPT_09_manual_too_big_runs_per_page_group(journey):
    orders = journey.manual("orders")
    assert orders is not None
    one_manual = len(render_corpus(journey, manuals=[orders]) + SYSTEM_PROMPT) // 4
    fake = small_provider(context_tokens=int(one_manual / 0.7 * 0.97))
    ConsistencyCheck().run(CheckContext(journey=journey, provider=fake))
    orders_calls = [c for c in fake.calls if "=== PAGE orders/" in c["cache_prefix"]]
    assert len(orders_calls) == 2
    assert all(c["cache_prefix"].count("=== PAGE ") == 1 for c in orders_calls)
    assert "page group 1 of 2" in orders_calls[0]["prompt"]


def test_AC_PROMPT_09_journey_single_manual_over_budget_uses_page_groups(single_manual):
    full = len(render_corpus(single_manual) + SYSTEM_PROMPT) // 4
    fake = small_provider(context_tokens=int(full / 0.7 * 0.97))
    TerminologyCheck().run(CheckContext(journey=single_manual, provider=fake))
    assert len(fake.calls) == 2


def test_AC_PROMPT_10_invalid_json_error_recorded_by_review_service(journey):
    fake = FakeProvider(lambda s, p, q: "this is not json" if "CONTRADICTIONS" in q else {"findings": []})
    run = ReviewService().review(journey, ["contradictions", "terminology"], provider=fake)
    errors = {e.check_id: e.message for e in run.errors}
    assert list(errors) == ["contradictions"] and "LlmError" in errors["contradictions"]
    assert "invalid structured output" in errors["contradictions"]
    assert run.llm_stats.calls == 2 and run.llm_stats.failed == 1 and run.llm_stats.valid_first_try == 1
    assert run.usage.calls == 3  # two attempts for contradictions, one for terminology


def test_AC_PROMPT_10_findings_verified_through_review_service(journey):
    fake = FakeProvider(lambda s, p, q: {"findings": [finding(locations=[
        {"page": "orders/create.md", "quote": "An order can be cancelled while it has the status Paid."},
        {"page": "delivery/statuses.md", "quote": "it can no longer be cancelled by the sales agent"}])]})
    run = ReviewService().review(journey, ["contradictions"], provider=fake)
    [f] = run.findings
    assert f.verified and f.source == "fake" and f.locations[0].line_start == 7


def test_AC_PROMPT_11_response_schema_shared_by_all_checks(journey):
    fake = FakeProvider()
    for cls in ALL:
        cls().run(CheckContext(journey=journey, provider=fake))
    assert {c["schema_name"] for c in fake.calls} == {"findings"}
    schema = FindingsResponse.model_json_schema()
    assert set(schema["properties"]) == {"findings"}


def test_AC_PROMPT_12_usage_and_stats_accumulate_in_context(journey):
    ctx = CheckContext(journey=journey, provider=FakeProvider())
    ConsistencyCheck().run(ctx)  # one call per manual
    assert ctx.usage.calls == 2 and ctx.usage.input_tokens > 0
    assert ctx.llm_stats.calls == 2 and ctx.llm_stats.valid_first_try == 2


def test_AC_PROMPT_12_check_without_provider_raises(journey):
    import pytest

    from umr.llm import LlmError
    with pytest.raises(LlmError, match="needs an LLM provider"):
        JourneyCheck().run(CheckContext(journey=journey))
