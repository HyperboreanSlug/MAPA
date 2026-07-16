"""Full scrape must keep paging and not silently stop after page 1."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from tests.smoke._path import ROOT  # noqa: F401


class FullScrapePagingTests(unittest.TestCase):
    def test_mugshots_state_pages_beyond_one(self):
        """scrape_state must not coerce max_pages=0 into max_pages=1."""
        from scraper.mugshotscom import MugshotsComScraper

        pages_seen: list[int] = []

        def fake_county(self, state, county, **kw):
            pages_seen.append(int(kw.get("max_pages") or 0))
            # One synthetic record so the state loop progresses.
            rec = {
                "source_url": f"https://mugshots.com/{state}/{county}/a",
                "source_system": "mugshotscom",
            }
            if kw.get("record_cb"):
                kw["record_cb"](rec, 1)
            return [rec]

        client = MagicMock()
        s = MugshotsComScraper(client=client, delay=0)
        with patch(
            "scraper.mugshotscom.scraper_county.discover_counties_for_state",
            return_value=["alpha", "beta"],
        ):
            with patch.object(MugshotsComScraper, "scrape_county", fake_county):
                out = s.scrape_state(
                    "tx",
                    max_pages=0,
                    with_photos=False,
                    workers=1,
                )
        self.assertEqual(len(out), 2)
        # Unlimited (0) must be forwarded, never forced to 1.
        self.assertEqual(pages_seen, [0, 0])

    def test_mugshots_scrape_all_unlimited_pages_when_no_row_limit(self):
        from scraper.mugshotscom import MugshotsComScraper

        pages_seen: list[int] = []

        def fake_state(self, state, **kw):
            pages_seen.append(int(kw.get("max_pages") or 0))
            return []

        client = MagicMock()
        s = MugshotsComScraper(client=client, delay=0)
        with patch(
            "scraper.mugshotscom.scraper_county.discover_states_from_site",
            return_value=["texas", "florida"],
        ):
            with patch.object(MugshotsComScraper, "scrape_state", fake_state):
                s.scrape(row_limit=0, with_photos=False, workers=1)
        self.assertEqual(pages_seen, [0, 0])

    def test_balanced_empty_catalog_falls_back(self):
        """Empty work-unit discovery must not return with zero hosts contacted."""
        from scraper.mugshot_sources.orchestrator import MultiSourceOrchestrator

        called: list[str] = []

        orch = MultiSourceOrchestrator(["recentlybooked"], delay=0)

        def fake_geo(sid, **kw):
            called.append(sid)
            return 0

        with patch.object(orch, "_discover_work_units", return_value=[]):
            with patch.object(orch, "_scrape_geo", side_effect=fake_geo):
                result = orch.scrape_balanced(scrape_all=True, with_photos=False)
        self.assertIn("recentlybooked", called)
        self.assertIn("recentlybooked", result.by_source)


if __name__ == "__main__":
    unittest.main()
