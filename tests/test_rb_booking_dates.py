"""RecentlyBooked booking date normalization for Browse visibility."""
from __future__ import annotations

import unittest

from scraper.recentlybooked.parse_util import (
    apply_booking_dates,
    normalize_booking_datetime,
)


class RbBookingDateTests(unittest.TestCase):
    def test_human_card_stamp(self):
        out = normalize_booking_datetime("July 6, 2026 8:50 PM")
        self.assertEqual(out.get("booking_date"), "2026-07-06")
        self.assertEqual(out.get("arrest_date"), "2026-07-06")
        self.assertEqual(out.get("arrest_time"), "20:50")

    def test_iso_passthrough(self):
        out = normalize_booking_datetime("2026-07-12T22:17:00.000")
        self.assertEqual(out.get("booking_date"), "2026-07-12")
        self.assertEqual(out.get("arrest_date"), "2026-07-12")

    def test_apply_fills_arrest_date(self):
        rec = {"booking_date": "July 12, 2026 2:24 PM"}
        apply_booking_dates(rec)
        self.assertEqual(rec["booking_date"], "2026-07-12")
        self.assertEqual(rec["arrest_date"], "2026-07-12")


if __name__ == "__main__":
    unittest.main()
