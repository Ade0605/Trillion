"""
Tests for memory recall. Stdlib unittest.

    python -m unittest trillion.tests_memory_recall

Embedding calls are mocked, so these run offline and deterministically. The
live semantic quality was verified separately against OmniRoute.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from . import memory_recall as mr
from .memory_store import FileMemoryStore


def _fake_vectors():
    """A tiny hand-made embedding space where 'reside' is near 'London'."""
    space = {
        "reside": [1.0, 0.0, 0.0],
        "london": [0.95, 0.1, 0.0],
        "pet": [0.0, 1.0, 0.0],
        "pixel": [0.0, 0.95, 0.1],
        "shade": [0.0, 0.0, 1.0],
        "teal": [0.1, 0.0, 0.95],
    }

    def embed(texts, timeout=6.0):
        out = []
        for t in texts:
            tl = t.lower()
            for key, vec in space.items():
                if key in tl:
                    out.append(vec)
                    break
            else:
                out.append([0.33, 0.33, 0.33])
        return out
    return embed


class Recall(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = FileMemoryStore(root=Path(self.tmp.name))
        self.store.add(hook="User resides in London", body="London.", mtype="user")
        self.store.add(hook="The pet is named Pixel", body="Pixel.", mtype="user")
        self.store.add(hook="Favourite shade is teal", body="Teal.", mtype="user")
        # point the cache at the temp dir
        self._cache_patch = mock.patch.object(mr, "_CACHE_PATH", Path(self.tmp.name) / ".emb.json")
        self._cache_patch.start()

    def tearDown(self):
        self._cache_patch.stop()
        self.tmp.cleanup()

    def test_semantic_paraphrase_hit(self):
        with mock.patch.object(mr, "embed_texts", _fake_vectors()):
            r = mr.recall("where does the person reside", self.store, k=1)
        self.assertEqual(r.mode, "semantic")
        self.assertIn("London", r.memories[0].hook)

    def test_keyword_fallback_when_embeddings_down(self):
        # embeddings return None → keyword path. Query shares a keyword.
        with mock.patch.object(mr, "embed_texts", lambda *a, **k: None):
            r = mr.recall("tell me about pixel the pet", self.store, k=1)
        self.assertEqual(r.mode, "keyword")
        self.assertIn("Pixel", r.memories[0].hook)

    def test_keyword_ranks_hook_over_body(self):
        with mock.patch.object(mr, "embed_texts", lambda *a, **k: None):
            r = mr.recall("teal", self.store, k=3)
        self.assertEqual(r.mode, "keyword")
        self.assertIn("teal", r.memories[0].hook.lower())

    def test_empty_store(self):
        empty = FileMemoryStore(root=Path(self.tmp.name) / "empty")
        r = mr.recall("anything", empty)
        self.assertEqual(r.mode, "empty")
        self.assertEqual(r.memories, [])

    def test_index_rebuildable_from_files(self):
        with mock.patch.object(mr, "embed_texts", _fake_vectors()):
            n, ok = mr.rebuild_embeddings(self.store)
        self.assertTrue(ok)
        self.assertEqual(n, 3)
        self.assertTrue((Path(self.tmp.name) / ".emb.json").exists())
        # delete the cache; recall still works by recomputing
        (Path(self.tmp.name) / ".emb.json").unlink()
        with mock.patch.object(mr, "embed_texts", _fake_vectors()):
            r = mr.recall("where does the person reside", self.store, k=1)
        self.assertEqual(r.mode, "semantic")

    def test_editing_a_memory_invalidates_its_vector(self):
        calls = {"n": 0}
        real = _fake_vectors()

        def counting(texts, timeout=6.0):
            calls["n"] += 1
            return real(texts)

        with mock.patch.object(mr, "embed_texts", counting):
            mr.recall("reside", self.store)          # embeds all 3 + query
            before = calls["n"]
            mr.recall("reside", self.store)          # cache warm: only the query
            self.store.update(next(m.slug for m in self.store.all()
                                   if "London" in m.hook), body="Now in Paris.")
            mr.recall("reside", self.store)          # the edited one re-embeds
        self.assertGreater(calls["n"], before)


if __name__ == "__main__":
    unittest.main()
