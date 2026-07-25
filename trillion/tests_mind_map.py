"""
Tests for the mind-map skeleton assembly. Stdlib unittest.

    python -m unittest trillion.tests_mind_map

The rule under test: never emit anything untrue. Empty sources → empty regions
(no placeholder nodes), a broken source empties only its region, and node detail
refuses paths outside the knowledge manifest.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from .memory_store import FileMemoryStore
from .mind_map import build_skeleton, node_detail


class Skeleton(unittest.TestCase):
    def test_empty_sources_only_core(self):
        sk = build_skeleton()
        regions = {n["region"] for n in sk["nodes"]}
        self.assertEqual(regions, {"core"})          # no invented nodes elsewhere
        self.assertEqual(sk["stats"]["memory_total"], 0)

    def test_no_similarity_edges_with_one_memory(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        s = FileMemoryStore(root=Path(tmp.name))
        s.add(hook="Lives in London", body="x", mtype="user")
        sk = build_skeleton(memory_store=s, embed_fn=lambda t: [[1.0]] * len(t))
        sim = [e for e in sk["edges"] if e["kind"] == "similarity"]
        self.assertEqual(sim, [])                     # 1 node → no web, not faked
        self.assertIn("too few", sk["stats"]["memory_edges"])
        # but a recall trunk to core always exists
        self.assertTrue(any(e["kind"] == "recall" for e in sk["edges"]))

    def test_similarity_web_with_real_vectors(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        s = FileMemoryStore(root=Path(tmp.name))
        s.add(hook="a", body="a", mtype="user")
        s.add(hook="b", body="b", mtype="user")
        s.add(hook="c", body="c", mtype="user")
        # a and b identical direction, c orthogonal → a-b edge, not a-c
        vecs = {"a\na": [1, 0], "b\nb": [1, 0], "c\nc": [0, 1]}
        sk = build_skeleton(memory_store=s, embed_fn=lambda t: [vecs[x] for x in t])
        sim = {(e["source"], e["target"]) for e in sk["edges"] if e["kind"] == "similarity"}
        self.assertIn(("mem:a", "mem:b"), sim)
        self.assertNotIn(("mem:a", "mem:c"), sim)
        self.assertEqual(sk["stats"]["memory_edges"], "semantic")

    def test_broken_memory_source_empties_only_that_region(self):
        class Boom:
            def all(self): raise RuntimeError("db down")
            def count(self): raise RuntimeError("db down")
        sk = build_skeleton(memory_store=Boom(),
                            knowledge_files=["AGENT.md"])
        self.assertEqual(sk["stats"].get("memory"), "error")
        # knowledge region still built
        self.assertTrue(any(n["region"] == "knowledge" for n in sk["nodes"]))

    def test_node_detail_manifest_only(self):
        # a path not in the manifest is refused (no directory traversal)
        self.assertIsNone(node_detail("know:.env", knowledge_files=["AGENT.md"]))
        # in-manifest path is allowed (content may or may not exist here)
        d = node_detail("know:AGENT.md", knowledge_files=["AGENT.md"])
        self.assertIsNotNone(d)
        self.assertEqual(d["type"], "knowledge")

    def test_node_detail_unknown_memory_is_none(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        s = FileMemoryStore(root=Path(tmp.name))
        self.assertIsNone(node_detail("mem:nope", memory_store=s))


if __name__ == "__main__":
    unittest.main()
