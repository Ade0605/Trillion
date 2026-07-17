"""
Tests for the self-knowledge machinery. Stdlib unittest (the project has no test
framework, so this imposes nothing new).

    python -m unittest trillion.self_knowledge.tests_self_knowledge
"""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

from . import drift as drift_module
from . import parser
from .generators import render_capabilities, render_integrations, render_recent
from .drift import LiveFacts, check as drift_check, DriftFinding, _page_routes


@dataclass
class _FakeTool:
    name: str
    description: str
    requires_confirmation: bool = False


class _FakeRegistry:
    def __init__(self, tools):
        self._tools = {t.name: t for t in tools}


SAMPLE = (
    "# Title\n\n"
    "Hand-written intro.\n\n"
    "<!-- AUTO-START: capabilities -->\n"
    "old capability body\n"
    "<!-- AUTO-END: capabilities -->\n\n"
    "Hand-written middle that must survive.\n\n"
    "<!-- AUTO-START: integrations -->\n"
    "old integrations body\n"
    "<!-- AUTO-END: integrations -->\n\n"
    "Hand-written footer.\n"
)


class RoundTripTests(unittest.TestCase):
    def test_serialize_is_exact_inverse_of_parse(self):
        self.assertEqual(parser.serialize(parser.parse(SAMPLE)), SAMPLE)

    def test_round_trip_with_crlf(self):
        crlf = SAMPLE.replace("\n", "\r\n")
        self.assertEqual(parser.serialize(parser.parse(crlf)), crlf)

    def test_block_names_in_order(self):
        self.assertEqual(parser.block_names(SAMPLE), ["capabilities", "integrations"])


class RenderTests(unittest.TestCase):
    def test_handwritten_survives_render(self):
        rendered = parser.render(SAMPLE, {
            "capabilities": lambda: "NEW CAPS",
            "integrations": lambda: "NEW INTEG",
        })
        self.assertIn("Hand-written intro.", rendered)
        self.assertIn("Hand-written middle that must survive.", rendered)
        self.assertIn("Hand-written footer.", rendered)
        self.assertIn("NEW CAPS", rendered)
        self.assertIn("NEW INTEG", rendered)
        self.assertNotIn("old capability body", rendered)
        self.assertNotIn("old integrations body", rendered)

    def test_render_is_idempotent(self):
        gens = {"capabilities": lambda: "NEW CAPS", "integrations": lambda: "NEW INTEG"}
        once = parser.render(SAMPLE, gens)
        twice = parser.render(once, gens)
        self.assertEqual(once, twice)

    def test_identity_generator_leaves_bodies_stable(self):
        # A generator echoing the canonical core keeps the doc stable.
        gens = {
            "capabilities": lambda: "old capability body",
            "integrations": lambda: "old integrations body",
        }
        once = parser.render(SAMPLE, gens)
        self.assertEqual(parser.render(once, gens), once)

    def test_unknown_block_left_untouched(self):
        doc = ("<!-- AUTO-START: mystery -->\nkeep me\n<!-- AUTO-END: mystery -->\n")
        self.assertEqual(parser.render(doc, {"capabilities": lambda: "x"}), doc)


class GeneratorTests(unittest.TestCase):
    def test_capabilities_lists_tool_from_fixture_registry(self):
        reg = _FakeRegistry([
            _FakeTool("add_reminder", "Add a reminder. Extra detail ignored.", True),
            _FakeTool("web_search", "Search the web and summarize.", False),
        ])
        out = render_capabilities(reg)
        self.assertIn("`add_reminder`", out)
        self.assertIn("`web_search`", out)
        self.assertIn("Add a reminder.", out)
        self.assertNotIn("Extra detail ignored", out)  # only first sentence
        self.assertIn("2 tools registered", out)

    def test_capabilities_handles_empty_registry(self):
        self.assertIn("No tools", render_capabilities(_FakeRegistry([])))

    def test_integrations_reports_missing_keys(self):
        out = render_integrations({"model": "claude-x", "elevenlabs_voice_id": "V1"})
        self.assertIn("Anthropic", out)
        self.assertIn("Deepgram", out)
        self.assertIn("ElevenLabs", out)
        self.assertIn("claude-x", out)


class DriftTests(unittest.TestCase):
    def test_clean_references_pass(self):
        # `Agent.run_turn` and `config.yml` really exist in the repo.
        doc = "## Identity\nThe `Agent.run_turn` method reads `config.yml`.\n"
        self.assertEqual(drift_check(doc), [])

    def test_missing_file_flagged(self):
        doc = "## Identity\nSee `trillion/ghost_file.py`.\n"
        findings = drift_check(doc)
        self.assertTrue(any(f.kind == "file" and "ghost_file" in f.reference for f in findings))

    def test_missing_symbol_flagged(self):
        doc = "## Identity\nCall `Agent.no_such_method`.\n"
        findings = drift_check(doc)
        self.assertTrue(any(f.kind == "symbol" for f in findings))

    def test_auto_blocks_are_not_checked(self):
        # A bogus reference inside an AUTO block must NOT be flagged.
        doc = ("<!-- AUTO-START: capabilities -->\n`trillion/ghost_file.py`\n"
               "<!-- AUTO-END: capabilities -->\n")
        self.assertEqual(drift_check(doc), [])

    def test_allowlisted_missing_file_is_not_flagged(self):
        # Runtime-generated, git-ignored paths (e.g. data/factory_agents.json)
        # are absent in a fresh checkout / CI. Listed in the allowlist, a
        # reference to one must not fail the path-existence check.
        doc = "## Identity\nVerify against `data/ghost_runtime_file.json`.\n"
        self.assertTrue(drift_check(doc))  # flagged without the allowlist
        with mock.patch.object(drift_module, "load_allowlist",
                               lambda: {"data/ghost_runtime_file.json"}):
            self.assertEqual(drift_check(doc), [])


# --------------------------------------------------------------------------- #
# Contradiction checks
# --------------------------------------------------------------------------- #

_FIVE_DOORS = ("/", "/cosmos", "/face", "/factory", "/phone")
_SAME = object()  # declared_tools mirrors the live registry unless overridden


def _facts(tools=("spawn_agent", "web_search"), routes=_FIVE_DOORS,
           declared=_SAME, agents=()) -> LiveFacts:
    """Live facts fixture. Pass None for a source the checker cannot read."""
    if declared is _SAME:
        declared = tools
    return LiveFacts(
        tools=None if tools is None else frozenset(tools),
        declared_tools=None if declared is None else frozenset(declared),
        page_routes=None if routes is None else tuple(routes),
        factory_agents=None if agents is None else tuple(agents),
    )


def _doc(body: str, heading: str = "Identity") -> str:
    return f"## {heading}\n\n{body}\n"


def _kinds(findings, kind):
    return [f for f in findings if f.kind == kind]


class NegativeClaimTests(unittest.TestCase):
    """Prose denying something the live registry proves exists."""

    def test_no_subagents_claim_flagged_when_spawn_agent_registered(self):
        # The exact wording that shipped before 2026-07-06.
        doc = _doc("No sub-agents or specialist personas exist yet.", "Sub-agents")
        findings = drift_check(doc, facts=_facts())
        self.assertTrue(_kinds(findings, "contradiction"))
        self.assertIn("spawn_agent", findings[0].reason)

    def test_single_agent_claim_flagged(self):
        doc = _doc("Trillion is a single agent.", "Sub-agents")
        self.assertTrue(_kinds(drift_check(doc, facts=_facts()), "contradiction"))

    def test_claim_split_across_a_hard_wrap_is_still_caught(self):
        # The doc is hard-wrapped at ~79 chars, so claims routinely span lines.
        doc = _doc("Trillion is a single\nagent.", "Sub-agents")
        self.assertTrue(_kinds(drift_check(doc, facts=_facts()), "contradiction"))

    def test_dispatch_tool_alone_is_evidence(self):
        doc = _doc("No sub-agents exist.", "Sub-agents")
        facts = _facts(tools=("web_search", "dispatch_to_notes-summarizer"))
        findings = drift_check(doc, facts=facts)
        self.assertTrue(_kinds(findings, "contradiction"))
        self.assertIn("dispatch_to_notes-summarizer", findings[0].reason)

    def test_cannot_spawn_claim_flagged(self):
        doc = _doc("Trillion cannot spawn sub-agents.", "Sub-agents")
        self.assertTrue(_kinds(drift_check(doc, facts=_facts()), "contradiction"))

    def test_true_negative_claim_is_not_flagged(self):
        # Nothing in the registry contradicts this, so it is simply true.
        doc = _doc("No sub-agents or specialist personas exist yet.", "Sub-agents")
        facts = _facts(tools=("web_search", "read_note"))
        self.assertEqual(drift_check(doc, facts=facts), [])

    def test_reversal_marker_suppresses_the_claim(self):
        # The fix for the original drift must not itself trip the checker.
        doc = _doc("Trillion is no longer a single agent — it mints specialists.",
                   "Sub-agents")
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_unreadable_registry_raises_nothing(self):
        doc = _doc("Trillion is a single agent.", "Sub-agents")
        self.assertEqual(drift_check(doc, facts=_facts(tools=None)), [])

    def test_unrelated_cannot_sentence_is_not_flagged(self):
        # Real prose from the doc: a limitation, not a denial of sub-agents.
        doc = _doc("Trillion cannot see its own live runtime state.")
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_no_tools_claim_flagged_against_populated_registry(self):
        doc = _doc("No tools are registered.")
        self.assertTrue(_kinds(drift_check(doc, facts=_facts()), "contradiction"))

    def test_contradictions_skip_auto_blocks(self):
        doc = ("<!-- AUTO-START: capabilities -->\n"
               "Trillion is a single agent. No sub-agents exist.\n"
               "<!-- AUTO-END: capabilities -->\n")
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_allowlisted_claim_is_suppressed(self):
        doc = _doc("Trillion is a single agent.", "Sub-agents")
        with mock.patch.object(drift_module, "load_allowlist",
                               lambda: {"is a single agent"}):
            self.assertEqual(drift_check(doc, facts=_facts()), [])


class CountClaimTests(unittest.TestCase):
    """Hard counts in prose vs. the live enumeration."""

    def test_wrong_front_door_count_flagged(self):
        # The exact wording that shipped before 2026-07-06.
        doc = _doc("There are three front doors sharing a single brain.")
        findings = _kinds(drift_check(doc, facts=_facts()), "count")
        self.assertTrue(findings)
        self.assertIn("prose says 3 front doors", findings[0].reason)
        self.assertIn("/cosmos", findings[0].reason)

    def test_correct_front_door_count_passes(self):
        doc = _doc("There are five front doors sharing a single brain.")
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_digits_and_adjectives_are_understood(self):
        doc = _doc("It serves 3 distinct front doors.")
        self.assertTrue(_kinds(drift_check(doc, facts=_facts()), "count"))

    def test_vague_quantifier_is_not_a_claim(self):
        doc = _doc("Several front doors share a single brain (Claude).")
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_wrong_tool_count_flagged_with_totality_marker(self):
        doc = _doc("There are seven tools registered.")  # the fixture has two
        findings = _kinds(drift_check(doc, facts=_facts()), "count")
        self.assertTrue(findings)
        self.assertIn("the registry holds 2", findings[0].reason)

    def test_correct_tool_count_passes(self):
        doc = _doc("There are two tools registered.")  # the fixture has two
        self.assertEqual(drift_check(doc, facts=_facts()), [])

    def test_bare_tool_count_is_treated_as_a_subset_not_a_total(self):
        # "the two tools that ask first" counts a subset — not drift.
        doc = _doc("Only the two tools that ask first will pause for you.")
        facts = _facts(tools=("a", "b", "c", "d"))
        self.assertEqual(drift_check(doc, facts=facts), [])

    def test_unreadable_route_table_raises_nothing(self):
        doc = _doc("There are three front doors.")
        self.assertEqual(drift_check(doc, facts=_facts(routes=None)), [])


class PartialRegistryTests(unittest.TestCase):
    """
    `build_registry` swallows failed optional imports, so the registry can come
    back short with no error — readable, but quietly wrong. The checker must not
    be fooled into silence, nor into flagging correct prose.
    """

    def test_claim_still_caught_when_registry_dropped_spawn_agent(self):
        doc = _doc("Trillion is a single agent.", "Sub-agents")
        partial = _facts(tools=("web_search",), declared=("web_search", "spawn_agent"))
        findings = drift_check(doc, facts=partial)
        self.assertTrue(_kinds(findings, "contradiction"))
        self.assertIn("spawn_agent", findings[0].reason)

    def test_factory_store_alone_is_evidence(self):
        doc = _doc("No sub-agents exist.", "Sub-agents")
        facts = _facts(tools=("web_search",), declared=("web_search",),
                       agents=("notes-summarizer",))
        findings = drift_check(doc, facts=facts)
        self.assertTrue(_kinds(findings, "contradiction"))
        self.assertIn("notes-summarizer", findings[0].reason)

    def test_partial_registry_forfeits_counting_authority(self):
        # Correct prose must not be flagged just because an import failed.
        doc = _doc("There are two tools registered.")
        partial = _facts(tools=("web_search",), declared=("web_search", "spawn_agent"))
        self.assertEqual(drift_check(doc, facts=partial), [])

    def test_complete_registry_still_counts(self):
        doc = _doc("There are nine tools registered.")
        facts = _facts(tools=("a", "b"), declared=("a", "b"))
        self.assertTrue(_kinds(drift_check(doc, facts=facts), "count"))

    def test_declared_tools_found_statically_in_this_repo(self):
        declared = drift_module._declared_tool_names()
        if declared is None:
            self.skipTest("source tree not readable from here")
        # Found by AST with no imports, so a broken optional dep can't hide it.
        self.assertIn("spawn_agent", declared)
        self.assertIn("draft_message", declared)  # register(name=...) shape


class FactoryStoreTests(unittest.TestCase):
    def _store(self, payload: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "factory_agents.json"
            path.write_text(payload, encoding="utf-8")
            return drift_module._active_factory_agents(path)

    def test_only_active_rows_count(self):
        payload = ('[{"slug": "live-one", "status": "active"},'
                   ' {"slug": "pending-one", "status": "pending"},'
                   ' {"slug": "dead-one", "status": "rejected"}]')
        self.assertEqual(self._store(payload), ("live-one",))

    def test_malformed_store_returns_none(self):
        self.assertIsNone(self._store("{not json"))

    def test_missing_store_returns_none(self):
        self.assertIsNone(drift_module._active_factory_agents(Path("no_such_store.json")))


_FAKE_SERVER = '''
from flask import Flask
app = Flask(__name__)

@app.get("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}

@app.get("/face")
def face():
    return "x", 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/legacy", methods=["GET"])
def legacy():
    return "x", 200, {"Content-Type": "text/html; charset=utf-8"}

@app.get("/voice-status")
def voice_status():
    return {"ok": True}

@app.get("/cosmos/agents")
def cosmos_agents():
    return {"agents": []}

@app.get("/sw.js")
def service_worker():
    return body, 200, {"Content-Type": "application/javascript"}

@app.get("/design/<project>/preview/<path:subpath>")
def design_preview(project, subpath):
    return "x", 200, {"Content-Type": "text/html; charset=utf-8"}

@app.post("/chat")
def chat():
    return "x", 200, {"Content-Type": "text/html; charset=utf-8"}

@app.route("/hook", methods=["POST"])
def hook():
    return "x", 200, {"Content-Type": "text/html; charset=utf-8"}
'''


class RouteEnumerationTests(unittest.TestCase):
    """A 'front door' is a GET route serving HTML — nothing else counts."""

    def _routes(self, source: str):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "fake_server.py"
            path.write_text(source, encoding="utf-8")
            return _page_routes(path)

    def test_only_html_get_routes_are_front_doors(self):
        self.assertEqual(self._routes(_FAKE_SERVER), ("/", "/face", "/legacy"))

    def test_unparseable_server_returns_none(self):
        self.assertIsNone(self._routes("def broken( ->"))

    def test_missing_server_returns_none(self):
        self.assertIsNone(_page_routes(Path("no_such_web_server.py")))

    def test_live_server_front_doors_match_the_doc(self):
        routes = _page_routes()
        if routes is None:
            self.skipTest("web_server.py not readable from here")
        self.assertEqual(routes, _FIVE_DOORS)


class RecentGeneratorTests(unittest.TestCase):
    def test_returns_string(self):
        out = render_recent()
        self.assertIsInstance(out, str)
        # either a table, a "no commits" note, or the unavailable placeholder
        self.assertTrue("|" in out or "commits" in out or "unavailable" in out)


if __name__ == "__main__":
    unittest.main()
