"""RecentlyBooked HTML parse fixture tests."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tests.smoke._path import ROOT


class RecentlyBookedParseTests(unittest.TestCase):
    def test_scrape_county_pages_past_known_urls(self):
        """Full scrape must not stop a county when page 1 is already in the DB."""
        from scraper.recentlybooked import RecentlyBookedScraper

        pages = {
            "1": [
                {
                    "source_url": "https://recentlybooked.com/xx/co/a~1",
                    "source_system": "recentlybooked",
                },
                {
                    "source_url": "https://recentlybooked.com/xx/co/b~1",
                    "source_system": "recentlybooked",
                },
            ],
            "2": [
                {
                    "source_url": "https://recentlybooked.com/xx/co/c~1",
                    "source_system": "recentlybooked",
                },
            ],
            "3": [],
        }

        client = MagicMock()
        client.get = lambda url: (
            url.rsplit("p=", 1)[-1] if "?p=" in url else "1"
        )

        with patch(
            "scraper.recentlybooked.scraper_scrape.parse_county_cards",
            side_effect=lambda html, *a, **k: list(pages.get(str(html), [])),
        ):
            s = RecentlyBookedScraper(client=client, delay=0)

            def _proc(card, **_kw):
                return dict(card)

            s._process_record = _proc  # type: ignore[method-assign]
            recs = s.scrape_county(
                "xx",
                "co",
                skip_existing_urls={
                    "https://recentlybooked.com/xx/co/a~1",
                    "https://recentlybooked.com/xx/co/b~1",
                },
                with_photos=False,
                with_html=False,
            )
        self.assertEqual(len(recs), 1)
        self.assertIn("/c~1", recs[0]["source_url"])

    def test_fixture_county_and_detail(self):
        from scraper.recentlybooked.parse import parse_county_cards, parse_detail

        fixtures = ROOT / "tests" / "fixtures"
        county = (fixtures / "recentlybooked_county.html").read_text(encoding="utf-8")
        cards = parse_county_cards(county)
        self.assertGreaterEqual(len(cards), 1)
        self.assertEqual(cards[0].get("source_system"), "recentlybooked")
        detail = (fixtures / "recentlybooked_detail.html").read_text(encoding="utf-8")
        rec = parse_detail(
            detail, "https://recentlybooked.com/xx/test-county/jane-doe~1_2"
        )
        self.assertEqual(rec.get("first_name"), "Jane")
        self.assertEqual(rec.get("last_name"), "Doe")
        self.assertTrue(rec.get("charge_description"))

    def test_homepage_mugshot_link_and_empty_booking_id(self):
        from scraper.recentlybooked.parse import parse_live_feed

        fixtures = ROOT / "tests" / "fixtures"
        html = (fixtures / "recentlybooked_live.html").read_text(encoding="utf-8")
        cards = parse_live_feed(html)
        self.assertEqual(len(cards), 2)
        self.assertEqual(cards[0]["county"], "broome")
        self.assertIn("location", cards[0])
        self.assertEqual(cards[1]["facility"], "1210")
        self.assertFalse(cards[1].get("booking_id"))

    def test_sitemap_locs_tolerate_misdecoded_bom(self):
        from scraper.recentlybooked.catalog import _sitemap_locs

        xml = (
            "ï»¿<?xml version=\"1.0\" encoding=\"utf-8\"?>"
            "<urlset xmlns=\"http://www.sitemaps.org/schemas/sitemap/0.9\">"
            "<url><loc>https://recentlybooked.com/nj/essex</loc></url>"
            "</urlset>"
        )
        locs = _sitemap_locs(xml)
        self.assertEqual(locs, ["https://recentlybooked.com/nj/essex"])

    def test_name_suffix_not_used_as_last_name(self):
        from scraper.recentlybooked.parse import _name_parts

        parts = _name_parts("Reginald Trail Jr")
        self.assertEqual(parts.get("last_name"), "Trail")
        self.assertEqual(parts.get("name_suffix"), "Jr")

    def test_production_detail_strong_fields_and_charges(self):
        from scraper.recentlybooked.parse import parse_detail

        fixtures = ROOT / "tests" / "fixtures"
        html = (fixtures / "recentlybooked_detail_live.html").read_text(encoding="utf-8")
        rec = parse_detail(
            html, "https://recentlybooked.com/tx/brazos/zohaib-ayub~235_370356"
        )
        self.assertEqual(rec.get("race"), "Middle Eastern")
        self.assertEqual(rec.get("sex"), "M")
        self.assertIn("POSS CS", rec.get("charge_description") or "")
        self.assertIn("POSS MARIJ", rec.get("charge_description") or "")


if __name__ == "__main__":
    unittest.main()
