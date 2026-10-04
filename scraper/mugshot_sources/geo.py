"""Discover county work units and scrape a single geo scope on one host."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Tuple

from .types import CancelCheck, ProgressCallback, RecordCallback


class GeoScrapeMixin:
    """Catalog discovery + per-source geographic scrape dispatch."""

    def _discover_work_units(
        self,
        *,
        state: Optional[str],
        scrape_all: bool,
    ) -> List[Tuple[str, str]]:
        """Use mugshots.com catalog when available, else RecentlyBooked."""
        units: List[Tuple[str, str]] = []
        # Prefer mugshots.com US-States index (rich coverage).
        if "mugshotscom" in self.source_ids:
            try:
                from scraper.mugshotscom import (
                    MugshotsComClient,
                    discover_counties_for_state,
                    discover_states_from_site,
                )
                from scraper.mugshotscom.catalog import state_slug_from_code

                with MugshotsComClient(delay=self.delay) as client:
                    if scrape_all:
                        states = discover_states_from_site(client)
                    elif state:
                        states = [state_slug_from_code(state)]
                    else:
                        states = []
                    for st in states:
                        for co in discover_counties_for_state(client, st):
                            units.append((st, co))
                if units:
                    return units
            except Exception:
                pass
        if "recentlybooked" in self.source_ids:
            try:
                from scraper.recentlybooked.catalog import (
                    discover_counties_for_state,
                    discover_states_from_homepage,
                )
                from scraper.recentlybooked.client import RecentlyBookedClient

                with RecentlyBookedClient(delay=self.delay) as client:
                    if scrape_all:
                        states = discover_states_from_homepage(client)
                    elif state:
                        states = [state.strip().lower()]
                    else:
                        states = []
                    for st in states:
                        for co in discover_counties_for_state(client, st):
                            units.append((st, co))
            except Exception:
                pass
        return units

    def _scrape_geo(
        self,
        source_id: str,
        *,
        state: Optional[str],
        county: Optional[str],
        scrape_all: bool,
        row_limit: int,
        workers: int,
        with_photos: bool,
        cancel_check: Optional[CancelCheck],
        record_cb: Optional[RecordCallback],
        progress_cb: Optional[ProgressCallback],
    ) -> int:
        known = self.identity.snapshot_urls()
        count = [0]
        _count_lock = threading.Lock()

        def cb(rec: Dict[str, Any], n: int) -> None:
            with _count_lock:
                count[0] += 1
            if record_cb:
                record_cb(rec, n)

        if source_id == "recentlybooked":
            from scraper.recentlybooked import RecentlyBookedScraper

            with RecentlyBookedScraper(delay=self.delay) as s:
                kw = dict(
                    with_photos=with_photos,
                    with_html=False,
                    skip_existing_urls=known,
                    cancel_check=cancel_check,
                    progress_cb=progress_cb,
                    record_cb=cb,
                    workers=max(1, workers),
                )
                if scrape_all:
                    s.scrape_all(**kw)
                elif county and state:
                    s.scrape_county(state, county, **kw)
                elif state:
                    s.scrape_state(state, **kw)
            return count[0]

        if source_id == "mugshotscom":
            from scraper.mugshotscom import MugshotsComScraper

            with MugshotsComScraper(delay=self.delay) as s:
                if scrape_all:
                    s.scrape(
                        row_limit=row_limit,
                        skip_existing_urls=known,
                        with_photos=with_photos,
                        cancel_check=cancel_check,
                        progress_cb=progress_cb,
                        record_cb=cb,
                        workers=max(1, workers),
                    )
                elif county and state:
                    s.scrape_county(
                        state,
                        county,
                        row_limit=row_limit,
                        max_pages=0,
                        skip_existing_urls=known,
                        with_photos=with_photos,
                        cancel_check=cancel_check,
                        progress_cb=progress_cb,
                        record_cb=cb,
                        workers=max(1, workers),
                    )
                elif state:
                    s.scrape_state(
                        state,
                        row_limit=row_limit,
                        skip_existing_urls=known,
                        with_photos=with_photos,
                        cancel_check=cancel_check,
                        progress_cb=progress_cb,
                        record_cb=cb,
                        workers=max(1, workers),
                    )
            return count[0]

        # City monitors run by separate forms. Skip them in county flow.
        if source_id in (
            "sf_sheriff",
            "nyc_doc",
            "hawaii_doc",
            "baltimore_dpscs",
            "alaska_doc",
        ):
            if progress_cb:
                try:
                    progress_cb(
                        0, None, {"label": f"{source_id} · city monitor skips county flow"}
                    )
                except Exception:
                    pass
            return 0

        if source_id == "bustednewspaper":
            from scraper.bustednewspaper import (
                BN_SSL_OUTAGE_MSG,
                BustedNewspaperScraper,
                BustedNewspaperUnavailable,
            )

            try:
                with BustedNewspaperScraper(delay=max(1.0, self.delay)) as s:
                    if scrape_all:
                        s.scrape(
                            row_limit=row_limit,
                            skip_existing_urls=known,
                            with_photos=with_photos,
                            cancel_check=cancel_check,
                            record_cb=cb,
                        )
                    elif county and state:
                        s.scrape_county(
                            state,
                            county,
                            row_limit=row_limit,
                            skip_existing_urls=known,
                            with_photos=with_photos,
                            cancel_check=cancel_check,
                            record_cb=cb,
                        )
                    elif state:
                        s.scrape_state(
                            state,
                            row_limit=row_limit,
                            skip_existing_urls=known,
                            with_photos=with_photos,
                            cancel_check=cancel_check,
                            record_cb=cb,
                        )
            except BustedNewspaperUnavailable as exc:
                raise RuntimeError(str(exc) or BN_SSL_OUTAGE_MSG) from exc
            return count[0]

        raise RuntimeError(f"Unsupported source {source_id!r}")
