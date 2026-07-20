"""MAPA ↔ SORPA export-card parity smoke checks."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class ExportParityTests(unittest.TestCase):
    def test_person_name_uppercase(self):
        from gui_app.shared.export_card_fields import person_name

        self.assertEqual(
            person_name({"first_name": "john", "last_name": "doe"}),
            "JOHN DOE",
        )

    def test_charge_separators_middle_dot(self):
        from gui_app.shared.export_card_polish import (
            card_charge_text,
            normalize_charge_separators,
        )

        self.assertEqual(
            normalize_charge_separators("Assault — Battery - Theft"),
            "Assault · Battery · Theft",
        )
        out = card_charge_text("ASSAULT — BATTERY")
        self.assertIn(" · ", out)
        self.assertNotIn("—", out)
        # Victim age ranges must not become charge separators
        self.assertEqual(
            normalize_charge_separators("Molestation Victim 12 - 15"),
            "Molestation Victim 12-15",
        )

    def test_jason_singh_card_charges(self):
        """FL multi-charge dump: sex first, no codes, alcohol short label."""
        from gui_app.shared.export_card_fields import crime

        raw = (
            "SELLING, GIVING, OR SERVING ALCOHOL BEVERAGE TO PERSON UNDER 21 "
            "(MISC0325); LEWD OR LASCIVIOUS CONDUCT (TOUCH) (DEFENDANT OVER 18) "
            "(LEWD1456); LEWD OR LASCIVIOUS MOLESTATION DEFENDANT OVER 18 "
            "VICTIM 12 - 15 (LEWD1454); LEWD OR LASCIVIOUS BATTERY (ENGAGE). "
            "(LEWD1401)"
        )
        out = crime({"charge_description": raw})
        low = out.lower()
        self.assertRegex(low, r"lewd|lascivious|molest|battery")
        self.assertIn("giving underage person alcohol", low)
        self.assertNotRegex(out, r"(?i)defendant\s+over")
        self.assertNotRegex(out, r"(?i)\b(?:lewd|leds|lews|misc)\s*\d{3,}")
        self.assertNotRegex(out, r"(?i)\(\s*(?:lewd|misc)\s*\d+")
        # Sex charges before alcohol
        alc_i = low.find("giving underage")
        sex_i = min(
            i
            for i in (
                low.find("lewd"),
                low.find("molest"),
                low.find("battery"),
            )
            if i >= 0
        )
        self.assertLess(sex_i, alc_i, msg=out)

    def test_export_number_assign_once(self):
        from gui_app.shared.export_card_release import (
            peek_release_number,
            release_number_for,
        )

        with tempfile.TemporaryDirectory() as td:
            store = Path(td) / "card_release.json"
            a = {"id": 1, "first_name": "A", "last_name": "Test", "state": "PA"}
            b = {"id": 2, "first_name": "B", "last_name": "Test", "state": "PA"}
            n1 = release_number_for(a, path=store, persist_db=False)
            n2 = release_number_for(a, path=store, persist_db=False)
            n3 = release_number_for(b, path=store, persist_db=False)
            self.assertEqual(n1, n2)
            self.assertNotEqual(n1, n3)
            self.assertIsNone(
                peek_release_number(
                    {"id": 99, "first_name": "Z", "last_name": "Nope"},
                    path=store,
                )
            )

    def test_export_confirm_marks_incorrect(self):
        from gui_app.shared.export_card_confirm import (
            mark_export_confirmed_incorrect,
        )

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "data").mkdir()
            rec = {"id": 7, "first_name": "X", "last_name": "Y"}
            with patch(
                "gui_app.shared.verdict_persist.persist_ethnicity_verdict",
                return_value=(True, '{"ethnicity_review":"incorrect"}', ""),
            ), patch("scraper.paths.project_root", return_value=root):
                ok = mark_export_confirmed_incorrect(
                    rec, db_path=str(root / "arrests.db")
                )
            self.assertTrue(ok)
            self.assertIn("incorrect", str(rec.get("flags") or ""))

    def test_mack_not_aa_without_aa_firstname(self):
        from scraper.ethnic_names import EthnicNameDatabase

        edb = EthnicNameDatabase()
        eth, _, _ = edb.classify_by_name(
            "Mack", first_name="Christopher", middle_name="David"
        )
        self.assertFalse(
            eth.startswith("African") or eth == "African American",
            f"got {eth}",
        )


if __name__ == "__main__":
    unittest.main()
