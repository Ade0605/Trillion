"""
Tier 1 tests: the dossier parser + the citation gate.

    python -m unittest trillion.board_advisors.tests_tier1
"""
from __future__ import annotations

import unittest

from .dossier import parse_dossier, load_seat, DossierError
from .gate import gate_citations, is_unsourced

_GOOD = """---
id: hormozi
name: Alex Hormozi
seat: Offers & Sales
domains: [pricing, offers, sales]
status: active
---
## Doctrine
### D1 — Grand Slam Offer
source: $100M Offers (2021), ch. 3
verification: sourced
Make an offer so good people feel stupid saying no.

### D2 — Price on value, not cost
source: $100M Offers (2021)
verification: sourced
Charge for the outcome, not the labour.

## Characteristic objection
Pushes back on discounting. Opens with: what is the dream outcome?

## Blind spots
Does not transfer to long government procurement cycles.

## Voice
Blunt, numbers-first, no hedging.
"""


class Parser(unittest.TestCase):
    def test_parses_a_good_dossier(self):
        s = parse_dossier(_GOOD, slug="hormozi")
        self.assertEqual(s.id, "hormozi")
        self.assertEqual(s.name, "Alex Hormozi")
        self.assertIn("pricing", s.domains)
        self.assertEqual(s.ids, {"D1", "D2"})
        self.assertEqual(s.doctrine[0].verification, "sourced")
        self.assertIn("dream outcome", s.objection)
        self.assertIn("procurement", s.blind_spots)

    def test_no_domains_rejected(self):
        bad = _GOOD.replace("domains: [pricing, offers, sales]\n", "")
        with self.assertRaises(DossierError) as e:
            parse_dossier(bad, slug="x")
        self.assertIn("domains", str(e.exception))

    def test_no_doctrine_rejected(self):
        bad = _GOOD.split("## Doctrine")[0] + "## Voice\nBlunt.\n"
        with self.assertRaises(DossierError) as e:
            parse_dossier(bad, slug="x")
        self.assertIn("doctrine", str(e.exception))

    def test_duplicate_ids_rejected_not_collapsed(self):
        bad = _GOOD.replace("### D2 — Price on value, not cost", "### D1 — Price on value, not cost")
        with self.assertRaises(DossierError) as e:
            parse_dossier(bad, slug="x")
        self.assertIn("duplicate", str(e.exception))

    def test_unknown_verification_falls_back_to_user(self):
        t = _GOOD.replace("verification: sourced", "verification: trust-me", 1)
        s = parse_dossier(t, slug="x")
        self.assertEqual(s.doctrine[0].verification, "user")

    def test_load_seat_never_raises(self):
        self.assertIsNone(load_seat("not a dossier", slug="bad"))   # logged, not raised


class Gate(unittest.TestCase):
    def test_fabricated_citation_stripped(self):
        self.assertEqual(gate_citations(["D1", "D9", "made-up"], {"D1", "D2"}), ["D1"])

    def test_normalize_dedupe_preserve_order(self):
        self.assertEqual(gate_citations(["d2", "D2", "d1"], {"D1", "D2"}), ["D2", "D1"])

    def test_withheld_id_stripped(self):
        # a real id, but not among the ids this seat was SHOWN
        self.assertEqual(gate_citations(["D3"], {"D1", "D2"}), [])

    def test_unsourced_flag(self):
        self.assertTrue(is_unsourced([], abstained=False))      # spoke, cited nothing
        self.assertFalse(is_unsourced([], abstained=True))      # abstained — fine
        self.assertFalse(is_unsourced(["D1"], abstained=False))


if __name__ == "__main__":
    unittest.main()
