"""
Tests pinning the speak_segment protocol. Stdlib unittest.

    python -m unittest trillion.tests_segments

These lock the shape the clients rely on: ordered seq, is_final only on the
last segment, one shared base_turn_id, and no fragment ever emitted mid-thought
(TTS speaking a half sentence sounds broken).
"""
from __future__ import annotations

import unittest

from .segments import SegmentEmitter, split_sentences


class Splitting(unittest.TestCase):
    def test_complete_sentences_and_remainder(self):
        s, rest = split_sentences("One. Two! Three? And a frag")
        self.assertEqual(s, ["One.", "Two!", "Three?"])
        self.assertEqual(rest, "And a frag")

    def test_no_terminator_is_all_remainder(self):
        s, rest = split_sentences("still going")
        self.assertEqual(s, [])
        self.assertEqual(rest, "still going")

    def test_abbreviations_do_not_split(self):
        s, _ = split_sentences("Mr. Smith arrived. ")
        self.assertEqual(s, ["Mr. Smith arrived."])

    def test_decimals_do_not_split(self):
        s, _ = split_sentences("It costs 3.50 today. ")
        self.assertEqual(s, ["It costs 3.50 today."])

    def test_empty(self):
        self.assertEqual(split_sentences(""), ([], ""))


class SegmentProtocol(unittest.TestCase):
    def _run(self, chunks):
        out = []
        em = SegmentEmitter(out.append, base_turn_id="base", record=None)
        for c in chunks:
            em.feed(c)
        em.finish()
        return out

    def test_single_sentence_is_one_final_segment(self):
        segs = self._run(["Yes."])
        self.assertEqual(len(segs), 1)
        self.assertTrue(segs[0]["is_final"])
        self.assertEqual(segs[0]["seq"], 0)
        self.assertEqual(segs[0]["text"], "Yes.")

    def test_multi_sentence_numbering_and_final_flag(self):
        segs = self._run(["First one. ", "Second one. ", "Third one."])
        self.assertEqual(len(segs), 3)
        self.assertEqual([s["seq"] for s in segs], [0, 1, 2])
        self.assertEqual([s["is_final"] for s in segs], [False, False, True])

    def test_all_share_one_base_turn_id(self):
        segs = self._run(["A. ", "B. ", "C."])
        self.assertEqual({s["base_turn_id"] for s in segs}, {"base"})
        self.assertEqual([s["turn_id"] for s in segs],
                         ["base::0", "base::1", "base::2"])

    def test_token_by_token_still_yields_whole_sentences(self):
        """The model streams tokens, not sentences — a segment must never be a
        fragment, or TTS speaks half a thought."""
        segs = self._run(list("Hello there. How are you?"))
        self.assertEqual([s["text"] for s in segs],
                         ["Hello there.", "How are you?"])
        self.assertEqual([s["is_final"] for s in segs], [False, True])

    def test_trailing_fragment_without_punctuation_is_flushed(self):
        segs = self._run(["Done. ", "no period here"])
        self.assertEqual([s["text"] for s in segs], ["Done.", "no period here"])
        self.assertTrue(segs[-1]["is_final"])

    def test_exactly_one_final_segment(self):
        segs = self._run(["A. ", "B. ", "C. ", "D."])
        self.assertEqual(sum(1 for s in segs if s["is_final"]), 1)

    def test_no_output_for_empty_stream(self):
        self.assertEqual(self._run([]), [])
        self.assertEqual(self._run(["", "   "]), [])

    def test_records_text_under_segment_id(self):
        store = {}
        em = SegmentEmitter(lambda e: None, base_turn_id="b",
                            record=lambda tid, txt: store.__setitem__(tid, txt))
        em.feed("One. Two.")
        em.finish()
        self.assertEqual(store, {"b::0": "One.", "b::1": "Two."})

    def test_full_text_is_preserved(self):
        em = SegmentEmitter(lambda e: None, base_turn_id="b")
        for c in ["Hello. ", "World."]:
            em.feed(c)
        self.assertEqual(em.finish(), "Hello. World.")

    def test_metric_present_on_every_segment(self):
        for s in self._run(["A. ", "B."]):
            self.assertIn("t_since_user", s)
            self.assertIsInstance(s["t_since_user"], float)


if __name__ == "__main__":
    unittest.main()
