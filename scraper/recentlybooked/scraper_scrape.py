"""RecentlyBooked scrape_live / scrape_county / scrape_state / scrape_all."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from .catalog import (
    BASE_URL,
    discover_counties_for_state,
    discover_counties_from_sitemap,
    discover_states_from_homepage,
)
from .parse import parse_county_cards


class RecentlyBookedScrapeMixin:
    """High-level scrape entry points."""

    def scrape_live(
        self,
        import_details: bool = True,
        with_photos: bool = True,
        with_html: bool = True,
        progress_cb=None,
        record_cb=None,
    ) -> List[Dict[str, Any]]:
        from .live_feed import fetch_live_feed

        records = fetch_live_feed(self.client, import_details=False)
        output: List[Dict[str, Any]] = []
        for record in records:
            done = self._process_record(
                record, import_details=import_details,
                with_photos=with_photos, with_html=with_html,
            )
            output.append(done)
            self._emit(record_cb, done, len(output))
            self._report(progress_cb, len(output))
        return output

    def scrape_county(
        self,
        state: str,
        county: str,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        with_html: bool = True,
        cancel_check=None,
        progress_cb=None,
        record_cb=None,
        workers: int = 1,
    ) -> List[Dict[str, Any]]:
        state, county = state.strip().lower(), county.strip().lower()
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
        records: List[Dict[str, Any]] = []
        page = 1
        prev_page_urls: Optional[frozenset] = None
        visited_pages: Set[str] = set()
        while not max_pages or page <= max_pages:
            if self._cancelled(cancel_check):
                break
            page_url = f"{BASE_URL}/{state}/{county}"
            if page > 1:
                page_url += f"?p={page}"
            if page_url in visited_pages:
                break
            visited_pages.add(page_url)
            loc = self._loc_label(
                state=state, county=county, page=page, source="recentlybooked"
            )
            ctx = {
                "state": state,
                "county": county,
                "page": page,
                "source": "recentlybooked",
                "label": loc,
            }
            self._report(progress_cb, len(records), ctx)
            cards = parse_county_cards(self.client.get(page_url))
            if not cards:
                break
            page_urls = frozenset(str(c.get("source_url") or "") for c in cards)
            if prev_page_urls is not None and page_urls == prev_page_urls:
                break
            prev_page_urls = page_urls
            fresh: List[Dict[str, Any]] = []
            for card in cards:
                if self._cancelled(cancel_check):
                    return records
                source_url = str(card["source_url"])
                if source_url in known_urls:
                    continue
                known_urls.add(source_url)
                card = dict(card)
                card["_scrape_loc"] = loc
                fresh.append(card)
            # Skip already-known detail URLs, but keep paging until the listing
            # is empty or repeats (do not stop just because this page was known).
            if not fresh:
                page += 1
                continue
            if workers == 1:
                for card in fresh:
                    if self._cancelled(cancel_check):
                        return records
                    done = self._process_record(
                        card, import_details=True,
                        with_photos=with_photos, with_html=with_html,
                    )
                    done["_scrape_loc"] = loc
                    records.append(done)
                    self._emit(record_cb, done, len(records))
                    self._report(progress_cb, len(records), ctx)
            else:
                self._process_cards_parallel(
                    fresh, workers=workers, with_photos=with_photos,
                    with_html=with_html, cancel_check=cancel_check,
                    progress_cb=progress_cb, record_cb=record_cb, records=records,
                    scrape_loc=loc, progress_context=ctx,
                )
            page += 1
        return records

    def scrape_state(
        self, state: str, max_pages: int = 0, skip_existing_urls=None,
        with_photos: bool = True, with_html: bool = True, cancel_check=None,
        progress_cb=None, record_cb=None, workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
        counties = [
            (state, county)
            for county in discover_counties_for_state(self.client, state)
        ]
        if workers == 1:
            return self._scrape_counties_serial(
                counties, max_pages=max_pages, known_urls=known_urls,
                with_photos=with_photos, with_html=with_html,
                cancel_check=cancel_check, progress_cb=progress_cb,
                record_cb=record_cb,
            )
        return self._scrape_counties_parallel(
            counties, workers=workers, max_pages=max_pages, known_urls=known_urls,
            with_photos=with_photos, with_html=with_html, cancel_check=cancel_check,
            progress_cb=progress_cb, record_cb=record_cb,
        )

    def scrape_all(
        self, limit_counties: int = 0, max_pages: int = 0, skip_existing_urls=None,
        with_photos: bool = True, with_html: bool = True, cancel_check=None,
        progress_cb=None, record_cb=None, workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known_urls = self._as_url_set(skip_existing_urls)
        workers = max(1, int(workers or 1))
        counties: List[tuple[str, str]] = []
        try:
            counties = list(discover_counties_from_sitemap(self.client))
        except Exception:
            counties = []
        if not counties:
            for st in discover_states_from_homepage(self.client):
                counties.extend(
                    (st, county)
                    for county in discover_counties_for_state(self.client, st)
                )
        if limit_counties:
            counties = counties[: int(limit_counties)]
        if workers == 1:
            return self._scrape_counties_serial(
                counties, max_pages=max_pages, known_urls=known_urls,
                with_photos=with_photos, with_html=with_html,
                cancel_check=cancel_check, progress_cb=progress_cb,
                record_cb=record_cb,
            )
        return self._scrape_counties_parallel(
            counties, workers=workers, max_pages=max_pages, known_urls=known_urls,
            with_photos=with_photos, with_html=with_html, cancel_check=cancel_check,
            progress_cb=progress_cb, record_cb=record_cb,
        )

    def _scrape_counties_serial(
        self, counties, *, max_pages, known_urls, with_photos, with_html,
        cancel_check, progress_cb, record_cb,
    ) -> List[Dict[str, Any]]:
        records: List[Dict[str, Any]] = []
        total = 0

        def _forward(rec: Dict[str, Any], _county_n: int) -> None:
            nonlocal total
            total += 1
            records.append(rec)
            self._emit(record_cb, rec, total)
            self._report(progress_cb, total)

        for state, county in counties:
            if self._cancelled(cancel_check):
                break
            loc = self._loc_label(
                state=state, county=county, source="recentlybooked"
            )
            self._report(
                progress_cb,
                total,
                {"state": state, "county": county, "label": loc},
            )
            self.scrape_county(
                state, county, max_pages=max_pages, skip_existing_urls=known_urls,
                with_photos=with_photos, with_html=with_html,
                cancel_check=cancel_check, progress_cb=progress_cb,
                record_cb=_forward, workers=1,
            )
        return records
