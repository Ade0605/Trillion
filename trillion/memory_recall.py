"""
Recall over the file-backed memories — semantic when possible, keyword always.

Semantic recall uses OmniRoute's local embeddings endpoint
(`gemini-embedding-001`, no key, loopback). When OmniRoute is down — it runs as
a logon task, so it often will be — recall silently falls back to keyword
overlap. It degrades, never breaks, and the mode it used is returned so the
caller can surface it rather than hide it.

**Top-k ranking, not an absolute threshold.** Measured on this model, a
paraphrase scored 0.653 against its target vs 0.503 for an unrelated line — a
0.15 gap. A fixed cutoff would either admit junk or reject good hits, so we rank
and take the top k.

The embedding cache (`data/memory/.embeddings.json`) is **derived and
rebuildable** — keyed by a fingerprint of each memory's text, so editing a
memory invalidates its vector automatically. It is never the source of truth;
the markdown files are.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import threading
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .memory_store import FileMemoryStore, Memory

_CACHE_PATH = Path(__file__).parent.parent / "data" / "memory" / ".embeddings.json"
_OMNIROUTE_URL = os.environ.get("OMNIROUTE_EMBED_URL", "http://127.0.0.1:20128/v1/embeddings")
_EMBED_MODEL = os.environ.get("OMNIROUTE_EMBED_MODEL", "gemini/gemini-embedding-001")
DEFAULT_K = 6

_lock = threading.RLock()
_STOP = {
    "the", "a", "an", "is", "are", "was", "were", "to", "of", "and", "or", "in",
    "on", "for", "my", "me", "i", "you", "your", "it", "that", "this", "with",
    "what", "who", "where", "when", "how", "do", "does", "did", "have", "has",
}


@dataclass
class RecallResult:
    memories: list[Memory] = field(default_factory=list)
    mode: str = "empty"          # "semantic" | "keyword" | "empty"
    scores: list[float] = field(default_factory=list)


def _fingerprint(m: Memory) -> str:
    return hashlib.sha1((m.hook + "\n" + m.body).encode("utf-8")).hexdigest()[:16]


def embed_texts(texts: list[str], timeout: float = 6.0) -> list[list[float]] | None:
    """Batch-embed via OmniRoute. Returns None on any failure (down, error,
    shape mismatch) so the caller can fall back to keyword."""
    if not texts:
        return []
    try:
        body = json.dumps({"model": _EMBED_MODEL, "input": texts}).encode("utf-8")
        req = urllib.request.Request(_OMNIROUTE_URL, data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            d = json.load(r)
        data = sorted(d["data"], key=lambda x: x.get("index", 0))
        vecs = [item["embedding"] for item in data]
        if len(vecs) != len(texts):
            return None
        return vecs
    except Exception:
        return None


def _load_cache() -> dict:
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        _CACHE_PATH.write_text(json.dumps(cache), encoding="utf-8")
    except Exception:
        pass


def _cos(a: list[float], b: list[float]) -> float:
    s = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return s / (na * nb) if na and nb else 0.0


def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in _STOP and len(w) > 1}


def _keyword_rank(query: str, mems: list[Memory], k: int) -> RecallResult:
    q = _tokens(query)
    if not q:
        return RecallResult(mode="keyword")
    scored = []
    for m in mems:
        hook_t = _tokens(m.hook)
        body_t = _tokens(m.body)
        # hook overlap weighted higher than body overlap
        score = 2.0 * len(q & hook_t) + 1.0 * len(q & body_t)
        if score > 0:
            scored.append((score, m))
    scored.sort(key=lambda t: t[0], reverse=True)
    top = scored[:k]
    return RecallResult(memories=[m for _, m in top], mode="keyword",
                        scores=[s for s, _ in top])


def recall(query: str, store: FileMemoryStore | None = None, k: int = DEFAULT_K) -> RecallResult:
    store = store or FileMemoryStore()
    mems = store.all()
    if not mems:
        return RecallResult(mode="empty")

    with _lock:
        cache = _load_cache()
        # (re)embed any memory whose text changed or was never embedded
        stale = [m for m in mems if cache.get(m.slug, {}).get("fp") != _fingerprint(m)]
        if stale:
            vecs = embed_texts([m.hook + "\n" + m.body for m in stale])
            if vecs:
                for m, v in zip(stale, vecs):
                    cache[m.slug] = {"fp": _fingerprint(m), "vec": v}
                # prune vectors for memories that no longer exist
                live = {m.slug for m in mems}
                for slug in [s for s in cache if s not in live]:
                    cache.pop(slug, None)
                _save_cache(cache)

        have_all = all(m.slug in cache and "vec" in cache[m.slug] for m in mems)
        qvec = embed_texts([query]) if have_all else None

    if qvec and have_all:
        qv = qvec[0]
        scored = [( _cos(qv, cache[m.slug]["vec"]), m) for m in mems]
        scored.sort(key=lambda t: t[0], reverse=True)
        top = scored[:k]
        return RecallResult(memories=[m for _, m in top], mode="semantic",
                            scores=[round(s, 3) for s, _ in top])

    # OmniRoute unavailable → keyword fallback
    return _keyword_rank(query, mems, k)


def rebuild_embeddings(store: FileMemoryStore | None = None) -> tuple[int, bool]:
    """Recompute the whole embedding cache from the files. Returns
    (memories_embedded, semantic_available)."""
    store = store or FileMemoryStore()
    mems = store.all()
    with _lock:
        if not mems:
            _save_cache({})
            return 0, False
        vecs = embed_texts([m.hook + "\n" + m.body for m in mems])
        if not vecs:
            return 0, False
        cache = {m.slug: {"fp": _fingerprint(m), "vec": v} for m, v in zip(mems, vecs)}
        _save_cache(cache)
        return len(cache), True
