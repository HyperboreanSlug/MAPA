"""Charge classification and charge-filtered misclass smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.charge_classifications import classify_charge, classify_record
from scraper.charge_expand import expand_charge, expand_charge_text
from scraper.charge_summary import summarize_charge
from scraper.database import Database
from scraper.searcher import ArrestSearcher


class ChargeFilterTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.create_in_memory()

    def tearDown(self):
        self.db.close()

    def test_charge_expand_no_abbreviations(self):
        full = expand_charge_text("A ASSLT CBI FV")
        self.assertIn("Assault Causes Bodily Injury Family Violence", full)
        self.assertNotIn("ASSLT", full)
        self.assertNotIn("CBI", full)
        self.assertNotRegex(full, r"\bFV\b")
        full2 = expand_charge_text("A UNL RESTRAINT FV")
        self.assertIn("Unlawful Restraint Family Violence", full2)
        self.assertNotIn("UNL", full2)
        multi = expand_charge(
            {"charge_description": "A ASSLT CBI FV; A UNL RESTRAINT FV"}
        )
        self.assertIn("Assault Causes Bodily Injury Family Violence", multi)
        self.assertIn("Unlawful Restraint Family Violence", multi)

    def test_charge_summaries_merge_aliases(self):
        for raw in (
            "ICE",
            "US IMMIGRATION",
            "IMMIGRATION HOLD",
            "immigration hold",
            "HOLD FOR ICE",
            "FEDERAL OFFENSE (IMMIGRATION)",
        ):
            self.assertEqual(
                summarize_charge(raw),
                "ICE IMMIGRATION HOLD",
                msg=raw,
            )
        self.assertEqual(summarize_charge("Fta"), "FAILURE TO APPEAR")
        self.assertEqual(
            summarize_charge("ICE; FAILURE TO APPEAR"),
            "ICE IMMIGRATION HOLD; FAILURE TO APPEAR",
        )
        self.assertEqual(
            summarize_charge({"charge_description": "D.U.I. (ALCOHOL)"}),
            "DUI / DWI",
        )
        # Abbreviated Texas booking codes → standardized table labels
        self.assertEqual(
            summarize_charge("A ASSLT CBI FV"),
            "DOMESTIC VIOLENCE",
        )
        self.assertEqual(
            summarize_charge("A ASSLT CBI FV; A UNL RESTRAINT FV"),
            "DOMESTIC VIOLENCE",
        )
        self.assertEqual(
            summarize_charge("UNL RESTRAINT"),
            "KIDNAPPING / FALSE IMPRISONMENT",
        )
        # Texas multi-charge booking line (card summary path)
        tx = (
            "EVADING ARREST DETENTION; FAIL TO ID FUGITIVE FRM JUSTICE "
            "REFUSE TO GIVE; MTR ENGAGING IN ORGANIZED CRIMINAL ACTIVITY"
        )
        labels = summarize_charge(tx)
        self.assertIn("EVADING ARREST", labels)
        self.assertIn("FAILURE TO IDENTIFY", labels)
        self.assertIn("ORGANIZED CRIMINAL ACTIVITY", labels)
        self.assertNotIn("Mtr", labels)
        from gui_app.shared.export_card_fields import crime

        card = crime({"charge_description": tx})
        self.assertIn("Evading Arrest", card)
        self.assertIn("Failure To Identify", card)
        self.assertLess(len(card), len(tx))
        self.assertEqual(
            summarize_charge("EVADING ARREST DET W/VEH"),
            "EVADING ARREST",
        )
        self.assertEqual(
            crime({"charge_description": "EVADING ARREST DET W/VEH"}),
            "Evading Arrest",
        )
        # KY-style OPER MV U/INFL ALC .08 → DUI on table + card
        for raw in (
            "Oper Mv U/INFL Alc . 08",
            "OPER MV U/INFL ALC .08 (189A.010(1A) 1ST",
            "OPER MTR VEHICAL U/INFL ALC .08",
        ):
            self.assertEqual(summarize_charge(raw), "DUI / DWI", msg=raw)
        multi = (
            "OPER MV U/INFL ALC .08 (189A.010(1A) 1ST; "
            "NO OPERATORS/MOPED LICENSE; "
            "ENDANGERING THE WELFARE OF A MINOR"
        )
        labels = summarize_charge(multi)
        self.assertIn("DUI / DWI", labels)
        self.assertIn("DRIVING WHILE SUSPENDED / REVOKED", labels)
        self.assertIn("CHILD ABUSE / ENDANGERMENT", labels)
        self.assertIn("DUI", crime({"charge_description": multi}))
        # Multi-charge FL booking → compact unique labels for cards
        fl = (
            "RESISTING OFFICER WITHOUT VIOLENCE; "
            "POSS. OF WEAPON IN COMMISSION OF FELONY; "
            "GRAND THEFT 3RD DEGREE-FIREARM; "
            "POSS. OF CANNABIS >20 GMS (WITH A WEAPON); "
            "FLEE/ELUDE POLICE-FLEE ELUDE LEO WITH LIGHTS SIREN ACTIVE"
        )
        fl_sum = summarize_charge(fl)
        self.assertIn("RESISTING ARREST", fl_sum)
        self.assertIn("WEAPONS OFFENSE", fl_sum)
        self.assertIn("THEFT / LARCENY", fl_sum)
        self.assertIn("POSSESSION OF MARIJUANA", fl_sum)
        self.assertIn("ELUDING / FLEEING", fl_sum)
        fl_card = crime({"charge_description": fl})
        self.assertLess(len(fl_card), len(fl))
        self.assertIn("Resisting", fl_card)
        # MTR - SEXUAL ASSLT + out-of-county docket noise → Sexual Assault only
        jr = "MTR - SEXUAL ASSLT; OUT OF COUNTY/JIM WELLS CO/20260031611/F"
        self.assertEqual(summarize_charge(jr), "SEXUAL ASSAULT")
        self.assertEqual(crime({"charge_description": jr}), "Sexual Assault")
        self.assertEqual(
            summarize_charge("OUT OF COUNTY HOLD"),
            "—",
        )
        self.assertIn(
            "POSSESSION OF MARIJUANA",
            summarize_charge("OUT OF COUNTY/POS MARIJ LT 2 OX/LAVACA C"),
        )

    def test_charge_classifications_and_filter(self):
        self.assertEqual(classify_charge("RAPE FIRST DEGREE"), "sex_crimes")
        self.assertEqual(classify_charge("Breaking and Entering a dwelling"), "burglary_be")
        self.assertEqual(classify_charge("BURGLARY OF HABITATION"), "burglary_be")
        self.assertEqual(classify_charge("Possession of cocaine"), "drugs")
        self.assertEqual(classify_charge("DUI alcohol"), "dui_traffic")
        self.assertEqual(classify_charge("Aggravated assault with firearm"), "weapons")
        self.assertEqual(classify_charge("Simple assault"), "violent")
        self.assertEqual(classify_charge(""), "unknown")

        batch = [
            {
                "first_name": "A", "last_name": "Garcia", "race": "White",
                "charge_description": "Sexual assault of a child",
                "state": "MD", "source_url": "c:1",
            },
            {
                "first_name": "B", "last_name": "Garcia", "race": "White",
                "charge_description": "Burglary second degree",
                "state": "MD", "source_url": "c:2",
            },
            {
                "first_name": "C", "last_name": "Smith", "race": "White",
                "charge_description": "Shoplifting",
                "state": "MD", "source_url": "c:3",
            },
        ]
        for r in batch:
            classify_record(r)
        self.assertEqual(batch[0]["charge_category"], "sex_crimes")
        self.assertEqual(batch[1]["charge_category"], "burglary_be")
        self.db.import_records(batch, skip_existing_urls=False)

        searcher = ArrestSearcher(db_path=":memory:")
        orphan = searcher.db
        searcher.db = self.db
        try:
            sex, base = searcher.analyze_ethnicities(
                min_confidence=0.5,
                ethnicity_filter="hispanic",
                charge_category="sex_crimes",
                return_base_count=True,
            )
            self.assertGreaterEqual(base, 1)
            names = {(m.record.get("last_name") or "").lower() for m in sex}
            self.assertIn("garcia", names)
            self.assertEqual(len(sex), 1)

            be_rows = self.db.search_records(charge_category="burglary_be", limit=50)
            self.assertEqual(len(be_rows), 1)
            self.assertIn("Burglary", be_rows[0].get("charge_description") or "")
        finally:
            searcher.db = orphan
            searcher.close()


if __name__ == "__main__":
    unittest.main()
