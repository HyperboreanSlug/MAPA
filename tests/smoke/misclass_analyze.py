"""Ethnic misclassification analysis smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.database import Database
from scraper.ethnic_names import EthnicNameDatabase
from scraper.searcher import ArrestSearcher


class MisclassAnalyzeTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.create_in_memory()

    def tearDown(self):
        self.db.close()

    def test_misclassify_primary_path(self):
        """Garcia recorded White → Hispanic misclass; Patel White → Indian."""
        batch = [
            {
                "first_name": "Juan",
                "last_name": "Garcia",
                "race": "White",
                "charge_description": "X",
                "state": "MD",
                "source_url": "t:1",
                "source_system": "t",
            },
            {
                "first_name": "Raj",
                "last_name": "Patel",
                "race": "White",
                "charge_description": "Y",
                "state": "MD",
                "source_url": "t:2",
                "source_system": "t",
            },
            {
                "first_name": "Bob",
                "last_name": "Smith",
                "race": "White",
                "charge_description": "Z",
                "state": "MD",
                "source_url": "t:3",
                "source_system": "t",
            },
            {
                "race": "White",
                "charge_description": "Anon",
                "state": "CA",
                "source_url": "t:4",
                "source_system": "t",
            },
        ]
        self.db.import_records(batch)
        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        try:
            hisp, base_h = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="hispanic",
                return_base_count=True,
            )
            names_h = {(m.record.get("last_name") or "").lower() for m in hisp}
            self.assertIn("garcia", names_h)
            self.assertGreaterEqual(base_h, 1)

            garcia = next(m for m in hisp if (m.record.get("last_name") or "").lower() == "garcia")
            self.db.update_arrest(
                int(garcia.record["id"]),
                {"flags": '{"ethnicity_review": "correct"}'},
            )
            hisp2, _ = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="hispanic",
                return_base_count=True,
            )
            names_h2 = {(m.record.get("last_name") or "").lower() for m in hisp2}
            self.assertNotIn("garcia", names_h2)

            # Confirmed correct only when confirmation filter requests it.
            hisp_ok, _ = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="hispanic",
                ethnicity_review="correct",
                return_base_count=True,
            )
            names_ok = {(m.record.get("last_name") or "").lower() for m in hisp_ok}
            self.assertIn("garcia", names_ok)

            indian, base_i = searcher.analyze_ethnicities(
                min_confidence=0.5,
                limit=0,
                ethnicity_filter="indian",
                return_base_count=True,
            )
            names_i = {(m.record.get("last_name") or "").lower() for m in indian}
            self.assertIn("patel", names_i)
            self.assertGreaterEqual(base_i, 1)
        finally:
            searcher.db = orphan
            searcher.close()

    def test_black_not_flagged_as_white_european(self):
        """Anglo surnames on Black records are not misclassifications."""
        from scraper.searcher import _is_compatible

        self.assertTrue(_is_compatible("European (english)", "Black"))
        self.assertTrue(_is_compatible("European (english)", "B"))
        self.assertTrue(_is_compatible("Jewish", "Black"))
        self.assertFalse(_is_compatible("Hispanic", "White"))
        self.assertFalse(_is_compatible("Hispanic", "Black"))

    def test_anglo_not_flagged_on_native_or_hispanic(self):
        """Anglo surnames on Native American / Hispanic are not misclassifications."""
        from scraper.searcher import _is_compatible

        self.assertTrue(_is_compatible("European (english)", "Native American"))
        self.assertTrue(_is_compatible("European (english)", "I"))
        self.assertTrue(_is_compatible("European (scottish)", "Hispanic"))
        self.assertTrue(_is_compatible("European (english)", "H"))
        self.assertTrue(_is_compatible("Jewish", "Asian"))
        self.assertTrue(_is_compatible("European (english)", "Other"))

    def test_filipino_spanish_not_high_asian(self):
        """Spanish colonial surnames only on Filipino list are not high Asian."""
        eth = EthnicNameDatabase()
        for first, last in (
            ("Mario", "Fernandez"),
            ("Alfredo", "Gonzales"),
            ("Jesus", "Alfaro"),
            ("Juan", "Andrada"),
            ("Richard", "Fernandez"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertFalse(
                e.startswith("Asian") and c >= 0.5,
                f"{first} {last} must not be high Asian (got {e} {c})",
            )
            # Prefer Hispanic so White→Hispanic product path still works.
            self.assertEqual(e, "Hispanic", f"{first} {last} → {e}")
            self.assertGreaterEqual(c, 0.5, f"{first} {last} conf {c}")
        # True East Asian surnames still flag as Asian
        e_ng, c_ng, _ = eth.classify_by_name("Nguyen", first_name="John")
        self.assertTrue(e_ng.startswith("Asian"), e_ng)
        self.assertGreaterEqual(c_ng, 0.5, c_ng)

    def test_martin_shared_hispanic_needs_hispanic_first(self):
        """Martin (English/French) is not high Hispanic without Hispanic first name."""
        eth = EthnicNameDatabase()
        e1, c1, _ = eth.classify_by_name("Martin", first_name="Christopher")
        self.assertFalse(
            e1 == "Hispanic" and c1 >= 0.5,
            f"Christopher Martin must not be high Hispanic (got {e1} {c1})",
        )
        e2, c2, _ = eth.classify_by_name("Martin", first_name="Jose")
        self.assertEqual(e2, "Hispanic")
        self.assertGreaterEqual(c2, 0.5, c2)

    def test_same_person_not_queued_twice(self):
        """Two bookings for the same person yield one misclass row; confirm hides both."""
        import tempfile
        from pathlib import Path

        from gui_app.shared.verdict_persist import persist_ethnicity_verdict

        tmp = Path(tempfile.mkdtemp()) / "person_once.db"
        db = Database(str(tmp))
        try:
            db.import_records(
                [
                    {
                        "first_name": "Juan",
                        "last_name": "Garcia",
                        "date_of_birth": "1991-03-03",
                        "race": "White",
                        "state": "TX",
                        "source_url": "dup:a",
                        "source_system": "t",
                        "booking_date": "2023-01-01",
                    },
                    {
                        "first_name": "Juan",
                        "last_name": "Garcia",
                        "date_of_birth": "1991-03-03",
                        "race": "White",
                        "state": "TX",
                        "source_url": "dup:b",
                        "source_system": "t",
                        "booking_date": "2023-08-01",
                    },
                ]
            )
            s = ArrestSearcher(str(tmp))
            try:
                hits = s.analyze_ethnicities(
                    min_confidence=0.5, limit=0, ethnicity_filter="hispanic"
                )
                self.assertEqual(len(hits), 1)
                ok, _, err = persist_ethnicity_verdict(
                    str(tmp), dict(hits[0].record), "correct"
                )
                self.assertTrue(ok, err)
                hits2 = s.analyze_ethnicities(
                    min_confidence=0.5, limit=0, ethnicity_filter="hispanic"
                )
                self.assertEqual(len(hits2), 0)
            finally:
                s.close()
        finally:
            db.close()

    def test_brown_eyes_brown_hair_boosts_hispanic_white(self):
        """Brown eyes + brown hair raises confidence for Hispanic×White."""
        from scraper.searcher_appearance import (
            apply_appearance_signals,
            appearance_adjustment,
            normalize_color,
        )

        self.assertEqual(normalize_color("BRO", kind="eye"), "brown")
        self.assertEqual(normalize_color("BLN", kind="hair"), "blond")
        d_boost, tags = appearance_adjustment("hispanic", "WHITE", "brown", "brown")
        self.assertGreater(d_boost, 0)
        self.assertTrue(any("brown" in t for t in tags))
        d_cut, tags_cut = appearance_adjustment("hispanic", "WHITE", "blue", "blond")
        self.assertLess(d_cut, 0)

        rec = {
            "race": "White",
            "eyes": "Brown",
            "hair": "Brown",
            "last_name": "Garcia",
        }
        conf, names, meta = apply_appearance_signals(
            rec, "Hispanic", 0.70, ["Garcia"], family="hispanic"
        )
        self.assertGreater(conf, 0.70)
        self.assertTrue(any("appearance:" in n for n in names))
        self.assertEqual(meta.get("eye"), "brown")
        self.assertIn("brown eyes + brown hair", rec.get("_appearance_note") or "")

    def test_ethnic_db_loads(self):
        eth = EthnicNameDatabase()
        self.assertTrue(eth.is_indian_surname("Singh") or eth.classify_by_name("Singh")[0].startswith("Indian"))
        self.assertEqual(eth.classify_by_name("Garcia")[0], "Hispanic")

    def test_asian_only_from_name_not_shared_white(self):
        """White people not marked Asian from name alone unless surname is only Asian."""
        eth = EthnicNameDatabase()
        # Shared White/Asian surnames: stay below default Analyze floor (0.5)
        for first, last in (
            ("James", "Lee"),
            ("John", "Park"),
            ("Mark", "Long"),
            ("Sarah", "Moon"),
            ("David", "Song"),
            ("John", "Law"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertFalse(
                e.startswith("Asian") and c >= 0.5,
                f"{first} {last} must not be high Asian conf (got {e} {c})",
            )
        # Multi-family European + Asian collision → not Asian from name alone
        e_bach, c_bach, _ = eth.classify_by_name("Bach", first_name="Hans")
        self.assertFalse(
            e_bach.startswith("Asian") and c_bach >= 0.5,
            f"Hans Bach must not be high Asian (got {e_bach} {c_bach})",
        )
        # Exclusively Asian surnames still flag (even with Anglo given names)
        for first, last in (
            ("John", "Nguyen"),
            ("John", "Wang"),
            ("John", "Chen"),
            ("John", "Tanaka"),
            ("John", "Kim"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertTrue(e.startswith("Asian"), f"{first} {last} → {e}")
            self.assertGreaterEqual(c, 0.5, f"{first} {last} conf {c}")

    def test_black_only_first_and_last_combo(self):
        """White people not marked Black unless Black-only first + last combo."""
        eth = EthnicNameDatabase()

        def is_black_high(e: str, c: float) -> bool:
            black = e == "African American" or e.startswith("African (")
            return black and c >= 0.5

        # Shared White/Black surnames — even with AA first names
        for first, last in (
            ("DeShawn", "Washington"),
            ("Jamal", "Jefferson"),
            ("Latasha", "Banks"),
            ("John", "Washington"),
            ("David", "Banks"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertFalse(
                is_black_high(e, c),
                f"{first} {last} must not be high Black conf (got {e} {c})",
            )
        # Uniquely Black/African surname alone is not enough without AA first
        for first, last in (
            ("John", "Mwangi"),
            ("John", "Adebayo"),
            ("John", "Okeke"),
            ("Michael", "Chukwu"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertFalse(
                is_black_high(e, c),
                f"{first} {last} needs Black-only first (got {e} {c})",
            )
        # Black-only first + uniquely Black last → high Black conf
        for first, last in (
            ("Jamal", "Adebayo"),
            ("DeShawn", "Okeke"),
            ("Latasha", "Chukwu"),
            ("Malik", "Mwangi"),
        ):
            e, c, _ = eth.classify_by_name(last, first_name=first)
            self.assertTrue(
                is_black_high(e, c),
                f"{first} {last} should be high Black (got {e} {c})",
            )

    def test_first_name_confidence_parity(self):
        """SOR parity: ambiguous Indian surname + Anglo first name is low conf."""
        eth = EthnicNameDatabase()
        e1, c1, _ = eth.classify_by_name("More", first_name="Cristobal")
        self.assertFalse(
            e1.startswith("Indian") and c1 >= 0.5,
            f"More+Cristobal should not be high Indian conf (got {e1} {c1})",
        )
        e2, c2, _ = eth.classify_by_name("Patel", first_name="Rahul")
        self.assertTrue(e2.startswith("Indian") or "Indian" in e2)
        self.assertGreaterEqual(c2, 0.5)

        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        self.db.import_records(
            [
                {
                    "first_name": "Cristobal",
                    "last_name": "More",
                    "race": "White",
                    "charge_description": "Theft",
                    "source_url": "fn:1",
                    "state": "FL",
                },
                {
                    "first_name": "Rahul",
                    "last_name": "Patel",
                    "race": "White",
                    "charge_description": "Theft",
                    "source_url": "fn:2",
                    "state": "FL",
                },
            ],
            skip_existing_urls=False,
        )
        try:
            results, base = searcher.analyze_ethnicities(
                min_confidence=0.5,
                ethnicity_filter="indian",
                return_base_count=True,
            )
            names = {
                (
                    (m.record.get("first_name") or ""),
                    (m.record.get("last_name") or "").lower(),
                )
                for m in results
            }
            self.assertIn(("Rahul", "patel"), names)
            self.assertNotIn(("Cristobal", "more"), names)
        finally:
            searcher.db = orphan
            searcher.close()


if __name__ == "__main__":
    unittest.main()
