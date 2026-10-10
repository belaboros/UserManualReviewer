"""Specs CONTRA, CONSIST, JOURNEY, TERM: registration, instructions, scope and post-processing."""

from umr.checks import CheckContext, CheckRegistry
from umr.checks.llm.consistency import ConsistencyCheck
from umr.checks.llm.contradictions import ContradictionsCheck
from umr.checks.llm.journey import JourneyCheck
from umr.checks.llm.procedures import ProceduresCheck
from umr.checks.llm.prompting import render_corpus
from umr.checks.llm.terminology import TerminologyCheck
from umr.domain import Category, Scope, Tier
from umr.llm.fake import FakeProvider


def loc(page, quote="some quote here"):
    return {"page": page, "quote": quote}


def respond(*findings):
    return FakeProvider(lambda s, p, q: {"findings": list(findings)})


def f(category, *locations, severity="major"):
    return {"category": category, "severity": severity, "title": "T", "explanation": "E",
            "suggested_fix": "F", "confidence": 0.8, "locations": list(locations)}


# ---------- CONTRA ----------

def test_AC_CONTRA_01_registered_journey_scope(journey, single_manual):
    assert CheckRegistry.get("contradictions") is ContradictionsCheck
    c = ContradictionsCheck()
    assert c.tier == Tier.LLM and c.scope == Scope.JOURNEY
    assert c.categories == (Category.CONTRADICTION, Category.VALUE_CONFLICT)
    assert c.applies_to(journey) and not c.applies_to(single_manual)


def test_AC_CONTRA_02_instruction_after_corpus(journey):
    fake = FakeProvider()
    ContradictionsCheck().run(CheckContext(journey=journey, provider=fake))
    [call] = fake.calls
    assert call["cache_prefix"] == render_corpus(journey)
    p = call["prompt"]
    assert "CONTRADICTIONS BETWEEN DIFFERENT MANUALS" in p and "- contradiction\n- value-conflict" in p
    for topic in ("statuses", "permissions", "timings", "limits", "channels", "opt-in/opt-out"):
        assert topic in p
    assert "at least two locations in DIFFERENT manuals" in p


def test_AC_CONTRA_03_needs_locations_in_two_manuals(journey):
    fake = respond(
        f("contradiction", loc("orders/create.md"), loc("delivery/statuses.md")),
        f("contradiction", loc("orders/create.md"), loc("orders/index.md")),
        f("contradiction", loc("orders/create.md")))
    found = ContradictionsCheck().run(CheckContext(journey=journey, provider=fake))
    assert len(found) == 1 and {x.manual_id for x in found[0].locations} == {"orders", "delivery"}


def test_AC_CONTRA_04_value_conflict_and_unknown_category(journey):
    fake = respond(f("value-conflict", loc("orders/create.md"), loc("delivery/statuses.md")),
                   f("terminology", loc("orders/index.md"), loc("delivery/index.md")))
    found = ContradictionsCheck().run(CheckContext(journey=journey, provider=fake))
    assert [x.category for x in found] == [Category.VALUE_CONFLICT, Category.CONTRADICTION]
    assert all(x.source == "fake" and x.check_id == "contradictions" for x in found)


# ---------- CONSIST ----------

def test_AC_CONSIST_01_registered_manual_scope(single_manual):
    c = ConsistencyCheck()
    assert CheckRegistry.get("consistency") is ConsistencyCheck
    assert c.tier == Tier.LLM and c.scope == Scope.MANUAL and c.applies_to(single_manual)
    assert set(c.categories) == {Category.INCONSISTENCY, Category.VALUE_CONFLICT, Category.STALE_VERSION,
                                 Category.UI_LABEL, Category.MALFORMED_CODE}
    assert c.categories[0] == Category.INCONSISTENCY


def test_AC_CONSIST_02_runs_once_per_manual(journey):
    fake = FakeProvider()
    ConsistencyCheck().run(CheckContext(journey=journey, provider=fake))
    assert len(fake.calls) == 2
    for call, manual in zip(fake.calls, journey.manuals, strict=True):
        assert call["cache_prefix"] == render_corpus(journey, manuals=[manual])
        assert f"Review only the manual '{manual.id}'" in call["prompt"]
        others = [m for m in journey.manuals if m is not manual]
        assert all(f"=== PAGE {m.id}/" not in call["cache_prefix"] for m in others)


def test_AC_CONSIST_03_instruction_covers_inconsistency_kinds(journey):
    p = ConsistencyCheck().instruction(ConsistencyCheck().plan(journey, FakeProvider())[0])
    for topic in ("timeouts", "ports", "file paths", "UI element", "role", "formats", "commands",
                  "template variables", "removed", "legacy", "versions", "REFERENCE"):
        assert topic in p
    for cat in ("inconsistency", "value-conflict", "stale-version", "ui-label", "malformed-code"):
        assert f"- {cat}\n" in p or p.endswith(f"- {cat}")


def test_AC_CONSIST_04_findings_mapped_per_manual(journey):
    fake = FakeProvider(lambda s, prefix, q: {"findings": [f("ui-label", loc("orders/create.md"))]}
                        if "=== PAGE orders/" in prefix else {"findings": []})
    found = ConsistencyCheck().run(CheckContext(journey=journey, provider=fake))
    assert [(x.category, x.locations[0].page_id) for x in found] == [(Category.UI_LABEL, "orders/create.md")]


def test_AC_CONSIST_05_procedures_step_order_check(journey):
    c = ProceduresCheck()
    assert CheckRegistry.get("procedures") is ProceduresCheck
    assert c.tier == Tier.LLM and c.scope == Scope.MANUAL and c.categories == (Category.STEP_ORDER,)
    fake = respond(f("whatever", loc("orders/create.md")))
    found = c.run(CheckContext(journey=journey, provider=fake))
    assert found and all(x.category == Category.STEP_ORDER for x in found)
    p = fake.calls[0]["prompt"]
    assert "STEP ORDER" in p and "LATER step" in p and "after the action" in p


def test_AC_CONSIST_06_manual_checks_share_the_cached_corpus(journey):
    fake = FakeProvider()
    ConsistencyCheck().run(CheckContext(journey=journey, provider=fake))
    ProceduresCheck().run(CheckContext(journey=journey, provider=fake))
    assert fake.calls[0]["cache_prefix"] == fake.calls[2]["cache_prefix"]
    assert fake.calls[1]["cache_prefix"] == fake.calls[3]["cache_prefix"]


# ---------- JOURNEY ----------

def test_AC_JOURNEY_01_registered_journey_scope(journey, single_manual):
    c = JourneyCheck()
    assert CheckRegistry.get("journey") is JourneyCheck
    assert c.tier == Tier.LLM and c.scope == Scope.JOURNEY
    assert c.categories == (Category.JOURNEY_GAP, Category.PREREQUISITE, Category.MISSING_ERROR_PATH)
    assert c.applies_to(journey) and not c.applies_to(single_manual)


def test_AC_JOURNEY_02_single_location_gap_accepted(journey):
    fake = respond(f("prerequisite", loc("orders/create.md", "Select the customer.")),
                   f("missing-error-path"), f("journey gap", loc("delivery/index.md")))
    found = JourneyCheck().run(CheckContext(journey=journey, provider=fake))
    assert [x.category for x in found] == [Category.PREREQUISITE, Category.JOURNEY_GAP]


def test_AC_JOURNEY_03_instruction_walks_the_journey(journey):
    fake = FakeProvider()
    JourneyCheck().run(CheckContext(journey=journey, provider=fake))
    p = fake.calls[0]["prompt"]
    assert "END-TO-END JOURNEY" in p
    for topic in ("hand-offs", "events", "states", "prerequisites", "how to obtain", "error and recovery",
                  "creates the expectation"):
        assert topic in p
    assert fake.calls[0]["cache_prefix"].startswith("JOURNEY: Test journey\nDESCRIPTION:")


# ---------- TERM ----------

def test_AC_TERM_01_registered(journey):
    c = TerminologyCheck()
    assert CheckRegistry.get("terminology") is TerminologyCheck
    assert c.tier == Tier.LLM and c.categories == (Category.TERMINOLOGY, Category.UNDEFINED_TERM)


def test_AC_TERM_02_applies_to_single_manual(single_manual):
    assert TerminologyCheck().applies_to(single_manual)
    fake = respond(f("undefined_term", loc("orders/create.md")))
    found = TerminologyCheck().run(CheckContext(journey=single_manual, provider=fake))
    assert len(fake.calls) == 1 and found[0].category == Category.UNDEFINED_TERM


def test_AC_TERM_03_instruction_covers_drift_and_undefined_terms(journey):
    fake = FakeProvider()
    TerminologyCheck().run(CheckContext(journey=journey, provider=fake))
    p = fake.calls[0]["prompt"]
    assert "same concept" in p and "different names" in p and "acronym" in p
    assert "one location per variant" in p and "never defined" in p
