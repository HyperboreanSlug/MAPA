"""RecentlyBooked Full Scrape per-source scraper dispatch."""
from __future__ import annotations

from typing import Set

from scraper.database import Database
from scraper.recentlybooked import RecentlyBookedScraper


class RbFullScrapeDispatchMixin:
    def _rb_full_run_scraper(
        self,
        *,
        source_id: str,
        state: str,
        county: str,
        scrape_all: bool,
        delay: float,
        workers: int,
        with_photos: bool,
        with_html: bool,
        known: Set[str],
        db: Database,
        on_record,
        on_progress,
    ) -> None:
        if source_id == "all":
            from scraper.mugshot_sources import (
                IdentityIndex,
                MultiSourceOrchestrator,
                list_mugshot_sources,
            )

            identity = IdentityIndex()
            identity.seed_from_db(db)
            for u in known:
                identity.add_url(u)
            avail = [s.id for s in list_mugshot_sources(available_only=True)]
            orch = MultiSourceOrchestrator(avail, delay=delay, identity=identity)
            multi = orch.scrape_balanced(
                state=state or None,
                county=county or None,
                scrape_all=scrape_all,
                workers_per_source=max(1, workers),
                skip_existing_urls=known,
                with_photos=with_photos,
                cancel_check=lambda: bool(
                    getattr(self, "rb_cancel", False)
                    or getattr(self, "_closing", False)
                ),
                record_cb=on_record,
                progress_cb=on_progress,
            )
            for sid, err in (multi.errors or {}).items():
                self.log_full(f"Full scrape {sid}: {err}")
            if multi.skipped_identity:
                self.log_full(
                    f"Full scrape: skipped {multi.skipped_identity} "
                    "cross-host identity duplicate(s)."
                )
            for sid, n in (multi.by_source or {}).items():
                self.log_full(f"Full scrape {sid}: {n} callback(s).")
            if not (multi.by_source or multi.errors):
                self.log_full(
                    "Full scrape multi-host: no work completed and no errors "
                    "reported (catalog may be empty)."
                )
        elif source_id == "bustednewspaper":
            from scraper.bustednewspaper import BustedNewspaperScraper

            bn_delay = max(1.0, float(delay))
            with BustedNewspaperScraper(delay=bn_delay) as s:
                bn_kw = dict(
                    with_photos=with_photos,
                    skip_existing_urls=known,
                    cancel_check=lambda: bool(
                        getattr(self, "rb_cancel", False)
                        or getattr(self, "_closing", False)
                    ),
                    progress_cb=on_progress,
                    record_cb=on_record,
                )
                if scrape_all:
                    s.scrape(**bn_kw)
                elif county:
                    s.scrape_county(state, county, **bn_kw)
                else:
                    s.scrape_state(state, **bn_kw)
        elif source_id == "mugshotscom":
            from scraper.mugshotscom import MugshotsComScraper

            with MugshotsComScraper(delay=delay) as s:
                ms_kw = dict(
                    with_photos=with_photos,
                    skip_existing_urls=known,
                    cancel_check=lambda: bool(
                        getattr(self, "rb_cancel", False)
                        or getattr(self, "_closing", False)
                    ),
                    progress_cb=on_progress,
                    record_cb=on_record,
                    workers=max(1, workers),
                )
                if scrape_all:
                    s.scrape(**ms_kw)
                elif county:
                    s.scrape_county(state, county, **ms_kw)
                else:
                    s.scrape_state(state, **ms_kw)
        else:
            with RecentlyBookedScraper(delay=delay) as s:
                kw = dict(
                    with_photos=with_photos,
                    with_html=with_html,
                    skip_existing_urls=known,
                    cancel_check=lambda: bool(
                        getattr(self, "rb_cancel", False)
                        or getattr(self, "_closing", False)
                    ),
                    progress_cb=on_progress,
                    record_cb=on_record,
                    workers=workers,
                )
                if scrape_all:
                    s.scrape_all(**kw)
                elif county:
                    s.scrape_county(state, county, **kw)
                else:
                    s.scrape_state(state, **kw)
