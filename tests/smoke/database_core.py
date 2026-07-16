"""Database import, search, and dedupe smoke tests."""
from __future__ import annotations

import unittest

from tests.smoke._path import ROOT  # noqa: F401

from scraper.config import get_bulk_sources, get_named_sources
from scraper.database import Database
from scraper.normalize import apply_field_map, stamp_source


class DatabaseCoreTests(unittest.TestCase):
    def setUp(self):
        self.db = Database.create_in_memory()

    def tearDown(self):
        self.db.close()

    def test_import_and_search(self):
        recs = [
            stamp_source(
                apply_field_map(
                    {
                        "First Name": "Juan",
                        "Last Name": "Garcia",
                        "Race": "White",
                        "Charge Description": "Assault",
                    },
                    {
                        "First Name": "first_name",
                        "Last Name": "last_name",
                        "Race": "race",
                        "Charge Description": "charge_description",
                    },
                ),
                source_id="demo",
                state="MD",
                jurisdiction="Demo",
            )
        ]
        recs[0]["source_url"] = "demo:1"
        r = self.db.import_records(recs)
        self.assertEqual(r["imported"], 1)
        rows = self.db.search_by_name("Garcia")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["race"], "White")

    def test_dedupe(self):
        self.db.import_records(
            [
                {"last_name": "A", "source_url": "u:1", "race": "W"},
                {"last_name": "A", "source_url": "u:1", "race": "B"},
                {"last_name": "B", "source_url": "u:2"},
            ],
            skip_existing_urls=False,
        )
        self.assertEqual(self.db.get_total_count(), 3)
        r = self.db.remove_duplicates("source_url", dry_run=False)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(self.db.get_total_count(), 2)

    def test_named_sources_exist(self):
        named = get_named_sources()
        self.assertTrue(any(s.id == "montgomery_md_arrests" for s in named))
        self.assertTrue(any(s.has_names for s in named))
        bulk = get_bulk_sources()
        self.assertGreaterEqual(len(bulk), 4)
        self.assertFalse(any(s.id == "bustednewspaper" for s in bulk))

    def test_ethnicity_verdict_persists_and_filters(self):
        """Confirmations write flags and verification filter finds them."""
        import tempfile
        from pathlib import Path

        from gui_app.shared.verdict_persist import persist_ethnicity_verdict
        from scraper.searcher import ethnicity_review_verdict

        tmp = Path(tempfile.mkdtemp()) / "verdict.db"
        db = Database(str(tmp))
        try:
            db.import_records(
                [
                    {
                        "first_name": "Juan",
                        "last_name": "Garcia",
                        "race": "White",
                        "source_url": "v:1",
                    }
                ]
            )
            row = db.search_records(limit=1)[0]
            rid = int(row["id"])
            ok, flags, err = persist_ethnicity_verdict(
                str(tmp), {"id": rid, "flags": None}, "correct"
            )
            self.assertTrue(ok, err)
            self.assertEqual(ethnicity_review_verdict({"flags": flags}), "correct")
            saved = dict(
                db._conn.execute(
                    "SELECT flags FROM arrests WHERE id = ?", (rid,)
                ).fetchone()
            )
            self.assertEqual(
                ethnicity_review_verdict({"flags": saved["flags"]}), "correct"
            )
            confirmed = db.search_records(ethnicity_review="correct", limit=0)
            self.assertEqual(len(confirmed), 1)
            unverified = db.search_records(ethnicity_review="unreviewed", limit=0)
            self.assertEqual(len(unverified), 0)
        finally:
            db.close()

    def test_verdict_propagates_to_identity_siblings(self):
        """Confirming one booking confirms same person (name+DOB) siblings."""
        import tempfile
        from pathlib import Path

        from gui_app.shared.verdict_persist import persist_ethnicity_verdict
        from scraper.searcher import ethnicity_review_verdict

        tmp = Path(tempfile.mkdtemp()) / "verdict_sib.db"
        db = Database(str(tmp))
        try:
            db.import_records(
                [
                    {
                        "first_name": "Juan",
                        "last_name": "Garcia",
                        "date_of_birth": "1990-01-15",
                        "race": "White",
                        "state": "FL",
                        "source_url": "sib:1",
                        "booking_date": "2024-01-01",
                    },
                    {
                        "first_name": "Juan",
                        "last_name": "Garcia",
                        "date_of_birth": "1990-01-15",
                        "race": "White",
                        "state": "FL",
                        "source_url": "sib:2",
                        "booking_date": "2024-06-01",
                    },
                    {
                        "first_name": "Other",
                        "last_name": "Person",
                        "date_of_birth": "1985-05-05",
                        "race": "White",
                        "state": "FL",
                        "source_url": "sib:3",
                    },
                ]
            )
            rows = db.search_records(limit=0)
            primary = next(r for r in rows if r["source_url"] == "sib:1")
            ok, _flags, err = persist_ethnicity_verdict(
                str(tmp), dict(primary), "incorrect"
            )
            self.assertTrue(ok, err)
            flags = {
                int(r["id"]): ethnicity_review_verdict(dict(r))
                for r in db._conn.execute(
                    "SELECT id, flags, source_url FROM arrests"
                ).fetchall()
            }
            # Both Garcia bookings confirmed; Other Person not.
            g_ids = [
                int(r["id"])
                for r in db._conn.execute(
                    "SELECT id, source_url FROM arrests"
                ).fetchall()
                if dict(r)["source_url"] in ("sib:1", "sib:2")
            ]
            o_id = next(
                int(r["id"])
                for r in db._conn.execute(
                    "SELECT id, source_url FROM arrests"
                ).fetchall()
                if dict(r)["source_url"] == "sib:3"
            )
            self.assertEqual(flags[g_ids[0]], "incorrect")
            self.assertEqual(flags[g_ids[1]], "incorrect")
            self.assertEqual(flags[o_id], "")
            unverified = db.search_records(ethnicity_review="unreviewed", limit=0)
            urls = {r.get("source_url") for r in unverified}
            self.assertNotIn("sib:1", urls)
            self.assertNotIn("sib:2", urls)
            self.assertIn("sib:3", urls)
        finally:
            db.close()

    def test_dedupe_merges_multi_state_charges(self):
        self.db.import_records(
            [
                {
                    "first_name": "A",
                    "last_name": "Same",
                    "date_of_birth": "1990-01-01",
                    "state": "FL",
                    "charge_description": "Burglary",
                    "source_url": "m:1",
                },
                {
                    "first_name": "A",
                    "last_name": "Same",
                    "date_of_birth": "1990-01-01",
                    "state": "TX",
                    "charge_description": "Theft",
                    "source_url": "m:2",
                    "race": "White",
                },
            ],
            skip_existing_urls=False,
        )
        r = self.db.remove_duplicates("name_dob", dry_run=False, merge_fields=True)
        self.assertEqual(r["deleted"], 1)
        self.assertEqual(self.db.get_total_count(), 1)
        row = list(self.db.iter_arrests())[0]
        states = (row.get("state") or "")
        self.assertIn("FL", states)
        self.assertIn("TX", states)
        charges = (row.get("charge_description") or "")
        self.assertIn("Burglary", charges)
        self.assertIn("Theft", charges)
        self.assertEqual(row.get("race"), "White")

    def test_dedupe_preserves_ethnicity_review_from_loser(self):
        """Confirmation on a deleted twin must land on the keeper."""
        from scraper.database.dedupe_merge_fields import DedupeMergeFieldsMixin
        from scraper.searcher import ethnicity_review_verdict

        keep = {
            "id": 1,
            "flags": None,
            "state": "TX",
            "charge_description": "Theft",
            "source_url": "keep:1",
        }
        loser = {
            "id": 2,
            "flags": (
                '{"ethnicity_review": "incorrect", '
                '"ethnicity_reviewed_at": "2026-01-01T00:00:00+00:00"}'
            ),
            "state": "FL",
            "charge_description": "Burglary",
            "source_url": "loser:2",
        }
        updates = DedupeMergeFieldsMixin.merge_duplicate_members(keep, [loser])
        self.assertIn("flags", updates)
        self.assertEqual(
            ethnicity_review_verdict({"flags": updates["flags"]}), "incorrect"
        )
        # Keep's own review still wins when both sides are set.
        keep2 = {
            "id": 3,
            "flags": '{"ethnicity_review": "correct"}',
            "state": "TX",
        }
        loser2 = {
            "id": 4,
            "flags": '{"ethnicity_review": "incorrect"}',
            "state": "FL",
        }
        updates2 = DedupeMergeFieldsMixin.merge_duplicate_members(keep2, [loser2])
        self.assertEqual(
            ethnicity_review_verdict({"flags": updates2["flags"]}), "correct"
        )


if __name__ == "__main__":
    unittest.main()
