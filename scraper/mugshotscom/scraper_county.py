"""County / state / multi-state scrape for mugshots.com."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Set

from .catalog import (
    BASE_URL,
    county_page_url,
    detail_urls_from_listing,
    discover_counties_for_state,
    discover_states_from_site,
    state_slug_from_code,
)
from .locked_set import LockedURLSet
from .parse import parse_listing_cards


class MugshotsComCountyMixin:
    def scrape_county(
        self,
        state: str,
        county: str,
        *,
        row_limit: int = 0,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check=None,
        progress_cb=None,
        record_cb=None,
        workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known = LockedURLSet(skip_existing_urls)
        records: List[Dict[str, Any]] = []
        lock = threading.Lock()
        page = 1
        workers = max(1, min(int(workers or 1), 16))
        prev_page_urls: Optional[frozenset] = None
        visited_pages: Set[str] = set()

        while not max_pages or page <= max_pages:
            if self._cancelled(cancel_check):
                break
            if row_limit and len(records) >= row_limit:
                break
            list_url = county_page_url(state, county, page)
            if list_url in visited_pages:
                break
            visited_pages.add(list_url)
            try:
                html = self.client.get(
                    list_url,
                    referer=f"{BASE_URL}/US-States/{state_slug_from_code(state)}/",
                )
            except Exception:
                break
            cards = parse_listing_cards(
                html, state_slug=state_slug_from_code(state), county_slug=county,
            )
            if not cards:
                urls = detail_urls_from_listing(html)
                cards = [{"source_url": u, "source_system": "mugshotscom"} for u in urls]
            if not cards:
                break
            page_urls = frozenset(
                str(c.get("source_url") or "") for c in cards if c.get("source_url")
            )
            if prev_page_urls is not None and page_urls == prev_page_urls:
                break
            prev_page_urls = page_urls

            batch = []
            for card in cards:
                url = str(card.get("source_url") or "")
                if not url or url in known:
                    continue
                known.add(url)
                card = dict(card)
                card["referer"] = list_url
                batch.append(card)
            # All cards already known (or empty page set) → stop; do not keep
            # requesting higher page numbers of the same listing.
            if not batch:
                break

            def work(card: Dict[str, Any]) -> Dict[str, Any]:
                return self._enrich(card, with_photos=with_photos)

            if workers == 1:
                for card in batch:
                    if self._cancelled(cancel_check):
                        return records
                    if row_limit and len(records) >= row_limit:
                        return records
                    done = work(card)
                    records.append(done)
                    if record_cb:
                        record_cb(done, len(records))
                    if progress_cb:
                        progress_cb(len(records), row_limit or None)
            else:
                with ThreadPoolExecutor(max_workers=workers) as pool:
                    futures = [pool.submit(work, c) for c in batch]
                    for fut in as_completed(futures):
                        if self._cancelled(cancel_check):
                            break
                        try:
                            done = fut.result()
                        except Exception as exc:
                            done = {
                                "scrape_error": str(exc),
                                "source_system": "mugshotscom",
                            }
                        with lock:
                            if row_limit and len(records) >= row_limit:
                                break
                            records.append(done)
                            n = len(records)
                        if record_cb:
                            record_cb(done, n)
                        if progress_cb:
                            progress_cb(n, row_limit or None)
            page += 1
        return records[:row_limit] if row_limit else records

    def scrape_state(
        self, state: str, *, row_limit: int = 0, max_pages: int = 0,
        skip_existing_urls=None, with_photos: bool = True, cancel_check=None,
        progress_cb=None, record_cb=None, workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        try:
            counties = discover_counties_for_state(self.client, state)
        except Exception:
            counties = []
        for county in counties:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not row_limit else max(0, row_limit - len(records))
            if row_limit and remaining == 0:
                break
            batch = self.scrape_county(
                state, county, row_limit=remaining or 0,
                max_pages=max_pages or 1, skip_existing_urls=known,
                with_photos=with_photos, cancel_check=cancel_check,
                progress_cb=None, record_cb=None, workers=workers,
            )
            for done in batch:
                records.append(done)
                url = str(done.get("source_url") or "")
                if url:
                    known.add(url)
                if record_cb:
                    record_cb(done, len(records))
                if progress_cb:
                    progress_cb(len(records), row_limit or None)
                if row_limit and len(records) >= row_limit:
                    return records[:row_limit]
        return records[:row_limit] if row_limit else records

    def scrape(
        self, row_limit: int = 0, *, skip_existing_urls=None, with_photos: bool = True,
        cancel_check=None, progress_cb=None, record_cb=None, workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        try:
            states = discover_states_from_site(self.client)
        except Exception:
            states = []
        for state in states:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not row_limit else max(0, row_limit - len(records))
            if row_limit and remaining == 0:
                break
            try:
                batch = self.scrape_state(
                    state, row_limit=remaining or 0,
                    max_pages=1 if row_limit else 0,
                    skip_existing_urls=known, with_photos=with_photos,
                    cancel_check=cancel_check, workers=workers,
                )
            except Exception:
                continue
            for done in batch:
                records.append(done)
                url = str(done.get("source_url") or "")
                if url:
                    known.add(url)
                if record_cb:
                    record_cb(done, len(records))
                if progress_cb:
                    progress_cb(len(records), row_limit or None)
                if row_limit and len(records) >= row_limit:
                    return records[:row_limit]
        return records[:row_limit] if row_limit else records
