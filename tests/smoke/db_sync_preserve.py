"""Local ethnic classification preservation during public DB sync."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from tests.smoke._path import ROOT


class DbSyncPreserveTests(unittest.TestCase):
    def test_delta_upsert_keeps_local_ethnicity_review(self):
        from scraper.db_sync_apply import apply_delta_ops
        from scraper.db_sync_keys import sync_record_key
        from scraper.database import Database

        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "t.db"
            db = Database(str(db_path))
            try:
                flags = json.dumps(
                    {
                        "ethnicity_review": "correct",
                        "ethnicity_reviewed_at": "2026-01-01T00:00:00+00:00",
                    },
                    sort_keys=True,
                )
                rec = {
                    "first_name": "Jane",
                    "last_name": "Doe",
                    "full_name": "Jane Doe",
                    "race": "White",
                    "state": "AZ",
                    "county": "apache",
                    "source_url": "https://recentlybooked.com/az/apache/jane-doe~1_2",
                    "source_system": "recentlybooked",
                    "flags": flags,
                    "charge_description": "local charge",
                }
                rid = db.insert_arrest(rec)
                self.assertGreater(rid, 0)
            finally:
                db.close()

            key = sync_record_key(rec)
            remote_row = {
                "first_name": "Jane",
                "last_name": "Doe",
                "full_name": "Jane Doe",
                "race": "White",
                "state": "AZ",
                "county": "apache",
                "source_url": rec["source_url"],
                "source_system": "recentlybooked",
                "flags": None,
                "charge_description": "remote charge update",
            }
            up, de, err = apply_delta_ops(
                db_path,
                [{"op": "upsert", "key": key, "row": remote_row}],
            )
            self.assertEqual((up, de, err), (1, 0, 0))

            conn = sqlite3.connect(str(db_path))
            try:
                row = conn.execute(
                    "SELECT charge_description, flags FROM arrests LIMIT 1"
                ).fetchone()
            finally:
                conn.close()
            self.assertEqual(row[0], "remote charge update")
            flags_out = json.loads(row[1] or "{}")
            self.assertEqual(flags_out.get("ethnicity_review"), "correct")

    def test_base_install_restores_overlays(self):
        from scraper.db_sync_preserve import (
            apply_overlays_to_db,
            extract_local_overlays,
            merge_overlay_into_row,
        )

        local = {
            "flags": json.dumps({"ethnicity_review": "incorrect", "race_manual": True}),
            "race": "Black",
            "likely_ethnicity": "african_american",
        }
        remote = {
            "flags": None,
            "race": "White",
            "likely_ethnicity": "european",
            "source_url": "https://example.com/x",
        }
        merged = merge_overlay_into_row(
            remote,
            {
                "flags": local["flags"],
                "protected": {
                    "ethnicity_review": "incorrect",
                    "race_manual": True,
                },
                "race": "Black",
                "likely_ethnicity": "african_american",
            },
        )
        self.assertEqual(merged["race"], "Black")
        self.assertIn("ethnicity_review", merged["flags"])


if __name__ == "__main__":
    unittest.main()
