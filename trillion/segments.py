"""
Per-sentence speech segments — the pipelining layer for voice latency.

The sequential path is: wait for the whole LLM reply, send it all to TTS, wait
for the whole MP3, download it, play. Every step blocks on the previous one
finishing, which is where the multi-second dead air comes from.

This module breaks the first gate. Sentences are emitted as they are produced,
so TTS for sentence 1 starts while the model is still writing sentence 2.

**Hold-one-ahead:** a segment is not emitted the moment it completes. It is
held until the *next* sentence arrives, which proves the held one was not the
last — so it goes out as `is_final=False`. Whatever is still held when the
stream ends is the final segment. This flags turn completion without an extra
protocol event, at the cost of delaying only the *final* segment. First-segment
latency (the number the user actually perceives) is unaffected.
"""
from __future__ import annotations

import re
import time
import uuid

# A sentence ends at . ! ? followed by whitespace or end-of-text. Common
# abbreviations and decimals are excluded so "Mr. Smith" / "3.5" don't split.
_ABBREV = r"(?<!\bMr)(?<!\bMrs)(?<!\bMs)(?<!\bDr)(?<!\bSt)(?<!\bvs)(?<!\be\.g)(?<!\bi\.e)(?<!\betc)"
_SENTENCE_END = re.compile(rf"{_ABBREV}(?<!\d)([.!?]+)(\s+|$)")


def split_sentences(text: str) -> tuple[list[str], str]:
    """Split into complete sentences plus the trailing incomplete remainder.

    Returns (sentences, remainder). The remainder is whatever follows the last
    terminator — held until more text arrives so TTS never speaks a fragment.
    """
    if not text:
        return [], ""
    sentences: list[str] = []
    last = 0
    for m in _SENTENCE_END.finditer(text):
        piece = text[last:m.end()].strip()
        if piece:
            sentences.append(piece)
        last = m.end()
    return sentences, text[last:]


class SegmentEmitter:
    """Turns a stream of text chunks into ordered `speak_segment` events.

    Usage:
        em = SegmentEmitter(emit)          # emit(dict) -> None
        for chunk in llm_stream:
            em.feed(chunk)
        em.finish()

    `emit` receives dicts shaped:
        {type, turn_id, base_turn_id, seq, is_final, text}
    where `turn_id` is `f"{base_turn_id}::{seq}"` — the id the client fetches
    TTS bytes for.
    """

    def __init__(self, emit, *, base_turn_id: str | None = None, record=None, clock=None):
        self._emit = emit
        self._record = record            # (turn_id, text) -> None; TTL store
        self._clock = clock or time.monotonic
        self.base_turn_id = base_turn_id or uuid.uuid4().hex[:16]
        self._buf = ""
        self._held: str | None = None
        self._held_seq: int | None = None
        self._seq = 0
        self._t0 = self._clock()
        self.emitted: list[dict] = []
        self.full_text = ""

    def feed(self, chunk: str) -> None:
        """Accept a chunk of model output; emit any sentence proven non-final."""
        if not chunk:
            return
        self.full_text += chunk
        self._buf += chunk
        sentences, self._buf = split_sentences(self._buf)
        for s in sentences:
            if self._held is not None:
                self._flush(self._held, self._held_seq, False)
            self._held, self._held_seq = s, self._seq
            self._seq += 1

    def finish(self) -> str:
        """Flush the held sentence (and any trailing fragment) as final."""
        tail = self._buf.strip()
        if tail:
            if self._held is not None:
                self._flush(self._held, self._held_seq, False)
            self._held, self._held_seq = tail, self._seq
            self._seq += 1
            self._buf = ""
        if self._held is not None:
            self._flush(self._held, self._held_seq, True)
            self._held = self._held_seq = None
        return self.full_text

    def _flush(self, text: str, seq: int, is_final: bool) -> None:
        turn_id = f"{self.base_turn_id}::{seq}"
        if self._record:
            self._record(turn_id, text)
        evt = {
            "type": "speak_segment",
            "turn_id": turn_id,
            "base_turn_id": self.base_turn_id,
            "seq": seq,
            "is_final": is_final,
            "text": text,
            # Headline metric: seconds from turn start to this segment being
            # speakable. seq=0 is the number that decides perceived latency.
            "t_since_user": round(self._clock() - self._t0, 3),
        }
        self.emitted.append(evt)
        self._emit(evt)
