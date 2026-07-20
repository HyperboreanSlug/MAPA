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
            "I.C.E Detainer",
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
        # All DUI-family strings → single DUI label
        for raw in (
            "D.U.I. (ALCOHOL)",
            "Oper Mv U/INFL Alc . 08",
            "OPER MV U/INFL ALC .08 (189A.010(1A) 1ST",
            "OPER MTR VEHICAL U/INFL ALC .08",
            "Operating While Intoxicated",
            "Operating a Vehicle While Intoxicated",
            "(MA) Operating a Vehicle While Intoxicated",
            "Driving Under Influence",
            "DRIVING UNDER THE INFLUENCE OF LIQUOR OR DRUGS",
            "OWI",
            "DWI",
        ):
            self.assertEqual(summarize_charge(raw), "DUI", msg=raw)
        self.assertEqual(
            summarize_charge("A ASSLT CBI FV"),
            "DOMESTIC VIOLENCE",
        )
        # AR statute wording is "battering", not "battery"
        for raw in (
            "Domestic Battering",
            "DOMESTIC BATTERING - 3RD DEGREE",
            "DOMESTIC BATTERING IN THE THIRD DEGREE - MISDEMEANOR",
            "TCA Description DOMESTIC BATTERING - 3RD DEGREE (M)",
        ):
            self.assertEqual(summarize_charge(raw), "DOMESTIC VIOLENCE", msg=raw)
        # Gerund "Holding" must match the same bucket as "Hold"
        for raw in (
            "Holding For Other Agency",
            "HOLDING FOR OTHER AGENCY",
            "HOLD FOR OTHER AGENCY",
            "O/W MISD: Outside Agency Wrnt",
        ):
            self.assertEqual(
                summarize_charge(raw),
                "HOLD FOR OTHER AGENCY",
                msg=raw,
            )
        self.assertEqual(
            summarize_charge("SEXUAL SOLICITATION OF A CHILD"),
            "SEX OFFENSE",
        )
        # PA IDSI and other sex crimes must not fall through to OTHER
        for raw in (
            "Involuntary Deviate Sexual Intercourse",
            "INVOLUNTARY DEVIATE SEXUAL INTERCOURSE",
            "3123 - INVOLUNTARY DEVIATE SEXUAL INTERCOURSE",
            "Deviate Sexual Intercourse",
            "Gross Sexual Imposition",
            "Corruption of Minors",
            "Indecency with a Child",
            "21.11 - INDECENCY WITH A CHILD",
            "Voyeurism",
            "Patronizing Prostitutes",
            "Sexual Contact",
            "Criminal Sexual Conduct 1st Degree",
        ):
            self.assertEqual(summarize_charge(raw), "SEX OFFENSE", msg=raw)
            self.assertEqual(
                __import__(
                    "scraper.charge_classifications", fromlist=["classify_charge"]
                ).classify_charge(raw),
                "sex_crimes",
                msg=raw,
            )
        # OTHER never coexists with a real summary label
        mixed = summarize_charge(
            "SEXUAL ASSAULT; ZZZ UNKNOWN FOOBAR CHARGE XYZ"
        )
        self.assertEqual(mixed, "SEX OFFENSE")
        self.assertNotIn("OTHER", mixed)
        self.assertEqual(
            summarize_charge("UNL RESTRAINT"),
            "KIDNAPPING / FALSE IMPRISONMENT",
        )
        self.assertEqual(
            summarize_charge("EVADING ARREST DET W/VEH"),
            "EVADING / FLEEING",
        )
        self.assertEqual(
            summarize_charge("MTR - SEXUAL ASSLT; OUT OF COUNTY/JIM WELLS CO/20260031611/F"),
            "SEX OFFENSE",
        )
        # Jail codes
        self.assertEqual(summarize_charge("UPOCS"), "POSSESSION OF CONTROLLED SUBSTANCE")
        self.assertEqual(summarize_charge("UPOM 2ND"), "POSSESSION OF MARIJUANA")
        self.assertEqual(summarize_charge("UPODP"), "DRUG PARAPHERNALIA")
        # Unmatched → OTHER (not raw docket text)
        self.assertEqual(summarize_charge("ZZZ UNKNOWN FOOBAR CHARGE XYZ"), "OTHER")
        from gui_app.shared.export_card_fields import crime

        # Cards use descriptive plain-language charges, not coarse table buckets.
        self.assertEqual(
            crime({"charge_description": "EVADING ARREST DET W/VEH"}),
            "Evading Arrest",
        )
        dui_card = crime(
            {
                "charge_description": (
                    "OPER MV U/INFL ALC .08; NO OPERATORS/MOPED LICENSE"
                )
            }
        )
        self.assertRegex(dui_card, r"(?i)under the influence|DUI|intoxicat")
        self.assertIn("No Operator License", dui_card)
        # Prefer real offense wording over "Sex Offense" bucket.
        sex_card = crime(
            {
                "charge_description": (
                    "ATTEMPT TO COMMIT AGGRAVATED SEXUAL ASSAULT CHILD"
                )
            }
        )
        self.assertRegex(sex_card, r"(?i)attempted")
        self.assertRegex(sex_card, r"(?i)sexual\s+assault")
        self.assertRegex(sex_card, r"(?i)child")
        self.assertNotEqual(sex_card.lower(), "sex offense")
        # Recover offense from raw_json when stored charge is a state stub.
        recovered = crime(
            {
                "charge_description": "Arkansas",
                "raw_json": (
                    '{"fields":{"Offense":'
                    '"ATTEMPT TO COMMIT AGGRAVATED SEXUAL ASSAULT CHILD"}}'
                ),
            }
        )
        self.assertRegex(recovered, r"(?i)attempted.*sexual\s+assault.*child")
        # FL alcohol + lewd dump: plain alcohol label; no defendant age / jail codes
        fl_card = crime(
            {
                "charge_description": (
                    "SELLING, GIVING, OR SERVING ALCOHOL BEVERAGE TO PERSON "
                    "UNDER 21 (MISC0325); LEWD OR LASCIVIOUS CONDUCT (TOUCH) "
                    "(DEFENDANT OVER 18) (LEWD1456); LEWD OR LASCIVIOUS "
                    "MOLESTATION DEFENDANT OVER 18 VICTIM 12 - 15 (LEWD1454)"
                )
            }
        )
        self.assertRegex(fl_card, r"(?i)giving underage alcohol")
        self.assertNotRegex(fl_card, r"(?i)defendant\s+over")
        self.assertNotRegex(fl_card, r"(?i)misc\s*\d|lewd\s*\d")
        self.assertLess(
            fl_card.lower().find("lewd"),
            fl_card.lower().find("giving underage"),
            msg=fl_card,
        )

    def test_charge_classifications_and_filter(self):
        self.assertEqual(classify_charge("RAPE FIRST DEGREE"), "sex_crimes")
        self.assertEqual(classify_charge("Breaking and Entering a dwelling"), "burglary_be")
        self.assertEqual(classify_charge("BURGLARY OF HABITATION"), "burglary_be")
        self.assertEqual(classify_charge("Possession of cocaine"), "drugs")
        self.assertEqual(classify_charge("DUI alcohol"), "dui_traffic")
        self.assertEqual(classify_charge("Aggravated assault with firearm"), "weapons")
        rec = {
            "charge_description": "BURGLARY OF A HABITATION",
            "charge_category": "",
        }
        self.assertEqual(classify_record(rec), "burglary_be")
        self.db.import_records(
            [
                {
                    "first_name": "A",
                    "last_name": "Garcia",
                    "race": "White",
                    "charge_description": "RAPE",
                    "charge_category": "sex_crimes",
                    "source_url": "t:sex",
                }
            ]
        )
        s = ArrestSearcher.__new__(ArrestSearcher)
        s.db = self.db
        from scraper.ethnic_names import EthnicNameDatabase

        s.ethnic_db = EthnicNameDatabase()
        try:
            hits = s.analyze_ethnicities(
                min_confidence=0.5,
                charge_category="sex_crimes",
                limit=0,
            )
            self.assertTrue(any((h.record or {}).get("last_name") == "Garcia" for h in hits))
        finally:
            s.ethnic_db = None


if __name__ == "__main__":
    unittest.main()
