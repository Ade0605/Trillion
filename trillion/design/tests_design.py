"""
Ship-tests for the head-of-design agent. Stdlib unittest.

    python -m unittest trillion.design.tests_design
"""
from __future__ import annotations

import shutil
import unittest
from pathlib import Path

from . import docs, design_tokens, scaffold, composer
from .claude_code_runner import ClaudeCodeResult

SLUG = "test-proj"


def _clean():
    root = docs.WORKSPACE_ROOT / SLUG
    if root.exists():
        shutil.rmtree(root, ignore_errors=True)


class Tier1Tokens(unittest.TestCase):
    def test_bootstrap_and_parse(self):
        _clean()
        docs.bootstrap_project(SLUG, "Test Proj")
        t = design_tokens.parse_tokens(docs.read_project_file(SLUG, "design.md"))
        self.assertEqual(t.fonts["display"], "Instrument Serif")
        self.assertTrue(all(v.startswith("#") for v in t.colors.values()))

    def test_forbidden_font_rejected(self):
        md = ("```yaml tokens\nfonts:\n  display: \"Poppins\"\n  body: \"Inter\"\n"
              "  mono: \"JetBrains Mono\"\ncolors:\n  background: \"#0a0a0b\"\n"
              "  foreground: \"#ededef\"\n  primary: \"#e5a663\"\n  muted: \"#17171a\"\n"
              "  border: \"#26262a\"\nshadcn:\n  base_color: \"neutral\"\n  style: \"new-york\"\n```")
        with self.assertRaises(design_tokens.TokenError):
            design_tokens.parse_tokens(md)


class Tier2Scaffold(unittest.TestCase):
    def test_scaffold_writes_13_and_idempotent(self):
        _clean(); docs.bootstrap_project(SLUG)
        root = docs.resolve_project_root(SLUG)
        t = design_tokens.parse_tokens(docs.read_project_file(SLUG, "design.md"))
        r1 = scaffold.prepare_scaffold(root, t, SLUG)
        self.assertFalse(r1["skipped"])
        self.assertEqual(len(r1["files"]), 13)
        cfg = (root / ".prism/preview/next.config.mjs").read_text()
        self.assertIn("trailingSlash: true", cfg)
        self.assertIn("output: 'export'", cfg)
        self.assertIn(f"/design/{SLUG}/preview", cfg)
        self.assertTrue((root / ".prism/preview/prism/component_catalog.md").exists())
        self.assertTrue(scaffold.prepare_scaffold(root, t, SLUG)["skipped"])


class Tier3And6And7(unittest.TestCase):
    def setUp(self):
        _clean(); docs.bootstrap_project(SLUG)
        self.captured = {}

    def _mock_runner(self, prompt, cwd, model=None, on_event=None, **kw):
        self.captured["prompt"] = prompt
        # simulate a successful build → create the expected static export
        out = Path(cwd) / "out" / "landing" / "hero" / "index.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text("<html>ok</html>", encoding="utf-8")
        return ClaudeCodeResult(ok=True, return_code=0, events=[{"type": "x"}])

    def test_dispatch_prompt_has_all_required_sections(self):
        res = composer.generate_mockup(
            feature_slug="landing", screen_name="hero",
            description="Landing hero for a voice assistant",
            visual_direction="grid-pattern at 0.5 opacity + drifting particles; voice waveform; breathing pulse",
            project=SLUG, _runner=self._mock_runner,
        )
        self.assertTrue(res.ok, res.error)
        self.assertEqual(res.screen_url, f"/design/{SLUG}/preview/landing/hero/")
        p = self.captured["prompt"]
        self.assertIn("THE BRIEF IS LAW", p)
        self.assertIn("Required visual elements", p)
        self.assertIn("opacity >= 0.4", p)
        self.assertIn("PRODUCT SURFACE", p)
        self.assertIn("Continuous motion", p)
        self.assertIn("npm run build", p)
        self.assertIn("design.md", p)
        self.assertIn("brief.md", p)
        self.assertIn("grid-pattern", p)  # from visual_direction + palette

    def test_references_appear_when_provided(self):
        # drop a fake reference image
        refdir = docs.resolve_project_root(SLUG) / ".prism/references/landing"
        refdir.mkdir(parents=True, exist_ok=True)
        (refdir / "ref1.png").write_bytes(b"\x89PNG\r\n")
        composer.generate_mockup(
            feature_slug="landing", screen_name="hero", description="x",
            reference_images=["ref1.png", "../evil.png"],  # 2nd must be rejected
            project=SLUG, _runner=self._mock_runner,
        )
        p = self.captured["prompt"]
        self.assertIn("READ THESE FIRST", p)
        self.assertIn("ref1.png", p)
        self.assertNotIn("evil.png", p)  # traversal rejected

    def test_invalid_tokens_bail_before_spawn(self):
        docs.write_design_doc(SLUG, "# no token block here")
        called = {"n": 0}
        def runner(*a, **k): called["n"] += 1; return ClaudeCodeResult(True, 0)
        res = composer.generate_mockup(feature_slug="landing", screen_name="hero",
                                       description="x", project=SLUG, _runner=runner)
        self.assertFalse(res.ok)
        self.assertIn("tokens invalid", res.error)
        self.assertEqual(called["n"], 0)  # never spawned CC

    @classmethod
    def tearDownClass(cls):
        _clean()


if __name__ == "__main__":
    unittest.main()
