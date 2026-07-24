"""
Tests for file-backed typed memory. Stdlib unittest.

    python -m unittest trillion.tests_memory_store
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from .memory_store import FileMemoryStore, migrate_from_json


class Store(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileMemoryStore(root=Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_add_writes_readable_file_with_type_hook_body(self):
        m = self.store.add(hook="User is based in London",
                           body="User is based in London.\n\n**Why:** timezone.",
                           mtype="user")
        p = Path(self.tmp.name) / f"{m.slug}.md"
        text = p.read_text(encoding="utf-8")
        self.assertIn("type: user", text)
        self.assertIn("hook: User is based in London", text)
        self.assertIn("**Why:** timezone.", text)

    def test_roundtrip_preserves_fields(self):
        self.store.add(hook="Prefers terse replies", body="Keep it short.",
                       mtype="feedback", source="conversation")
        got = self.store.all()[0]
        self.assertEqual(got.type, "feedback")
        self.assertEqual(got.hook, "Prefers terse replies")
        self.assertEqual(got.source, "conversation")
        self.assertIn("Keep it short.", got.body)

    def test_unknown_type_falls_back_to_user(self):
        m = self.store.add(hook="x", body="y", mtype="nonsense")
        self.assertEqual(m.type, "user")

    def test_slugs_are_unique(self):
        a = self.store.add(hook="same hook", body="1")
        b = self.store.add(hook="same hook", body="2")
        self.assertNotEqual(a.slug, b.slug)
        self.assertEqual(self.store.count(), 2)

    def test_index_lists_hooks_grouped_by_type(self):
        self.store.add(hook="lives in London", body="x", mtype="user")
        self.store.add(hook="wants terse replies", body="y", mtype="feedback")
        idx = (Path(self.tmp.name) / "INDEX.md").read_text(encoding="utf-8")
        self.assertIn("## user", idx)
        self.assertIn("## feedback", idx)
        self.assertIn("lives in London", idx)
        self.assertIn("never the source of truth", idx)

    def test_index_is_rebuildable_from_files(self):
        self.store.add(hook="a", body="1")
        (Path(self.tmp.name) / "INDEX.md").unlink()
        self.store.rebuild_index()
        self.assertTrue((Path(self.tmp.name) / "INDEX.md").exists())

    def test_delete_removes_file_and_updates_index(self):
        m = self.store.add(hook="temp fact", body="x")
        self.assertTrue(self.store.delete(m.slug))
        self.assertEqual(self.store.count(), 0)
        self.assertFalse((Path(self.tmp.name) / f"{m.slug}.md").exists())

    def test_hand_edited_file_without_frontmatter_loads(self):
        (Path(self.tmp.name) / "raw.md").write_text("just a bare fact\n", encoding="utf-8")
        mems = self.store.all()
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0].type, "user")   # default
        self.assertTrue(mems[0].hook)

    def test_update(self):
        m = self.store.add(hook="old", body="old body", mtype="user")
        self.store.update(m.slug, hook="new", body="new body", mtype="project")
        got = self.store.get(m.slug)
        self.assertEqual(got.hook, "new")
        self.assertEqual(got.type, "project")
        self.assertIn("new body", got.body)


class Migration(unittest.TestCase):
    def test_migrates_legacy_json_once(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        store = FileMemoryStore(root=root / "memory")
        legacy = root / "memory.json"
        legacy.write_text(json.dumps([
            {"id": "a", "statement": "User is based in London.", "created_at": "2026-06-29T13:04:11", "deleted": False},
            {"id": "b", "statement": "deleted fact", "deleted": True},
        ]), encoding="utf-8")

        n = migrate_from_json(store, json_path=legacy)
        self.assertEqual(n, 1)                       # deleted one skipped
        mems = store.all()
        self.assertEqual(len(mems), 1)
        self.assertEqual(mems[0].type, "user")
        self.assertIn("London", mems[0].hook)
        self.assertTrue(legacy.exists())             # legacy left intact

        # idempotent — a second run imports nothing
        self.assertEqual(migrate_from_json(store, json_path=legacy), 0)


if __name__ == "__main__":
    unittest.main()
