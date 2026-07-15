"""Busted Newspaper scrape_county / scrape_state / scrape methods."""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set

from .catalog import county_page_url, discover_counties_for_state, discover_states_from_homepage
from .parse import parse_county_cards
from .scraper_core import CancelCheck, ProgressCallback


class BustedNewspaperScraperRun:
    def scrape_live(
        self,
        *,
        row_limit: int = 20,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[Callable[[Dict[str, Any], int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Lightweight live poll: walk recent county pages until *row_limit*."""
        return self.scrape(
            row_limit=max(1, int(row_limit or 20)),
            skip_existing_urls=skip_existing_urls,
            with_photos=with_photos,
            cancel_check=cancel_check,
            progress_cb=progress_cb,
            record_cb=record_cb,
        )

    def scrape_county(
        self,
        state: str,
        county: str,
        *,
        row_limit: int = 0,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[Callable[[Dict[str, Any], int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape one county until ``row_limit`` or ``max_pages`` is reached."""
        state = state.strip().lower()
        county = county.strip().lower()
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        page = 1
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
            loc = f"bustednewspaper · {state}/{county} · p{page}"
            if progress_cb:
                try:
                    progress_cb(
                        len(records),
                        row_limit or None,
                        {
                            "state": state,
                            "county": county,
                            "page": page,
                            "source": "bustednewspaper",
                            "label": loc,
                        },
                    )
                except TypeError:
                    progress_cb(len(records), row_limit or None)
            try:
                html = self.client.get(
                    list_url,
                    referer=f"https://bustednewspaper.com/mugshots/{state}/",
                )
            except Exception:
                break
            cards = parse_county_cards(
                html,
                state_slug=state,
                county_slug=county,
            )
            if not cards:
                break
            page_urls = frozenset(
                str(c.get("source_url") or "") for c in cards if c.get("source_url")
            )
            if prev_page_urls is not None and page_urls == prev_page_urls:
                break
            prev_page_urls = page_urls
            for card in cards:
                if self._cancelled(cancel_check):
                    return records
                if row_limit and len(records) >= row_limit:
                    return records
                source_url = str(card["source_url"])
                if source_url in known:
                    continue
                known.add(source_url)
                card = dict(card)
                card["_scrape_loc"] = loc
                done = self._enrich_record(card, with_photos=with_photos)
                done["_scrape_loc"] = loc
                records.append(done)
                if record_cb:
                    record_cb(done, len(records))
                if progress_cb:
                    try:
                        progress_cb(
                            len(records),
                            row_limit or None,
                            {
                                "state": state,
                                "county": county,
                                "page": page,
                                "source": "bustednewspaper",
                                "label": loc,
                            },
                        )
                    except TypeError:
                        progress_cb(len(records), row_limit or None)
            # Keep paging past already-known listing pages until empty/repeat.
            page += 1
        return records

    def scrape_state(
        self,
        state: str,
        *,
        row_limit: int = 0,
        max_pages: int = 0,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[Callable[[Dict[str, Any], int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Scrape every discovered county in one state slug (e.g. ``texas``)."""
        state = state.strip().lower()
        cap = int(row_limit or 0)
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        try:
            counties = discover_counties_for_state(self.client, state)
        except Exception:
            counties = []
        for county in counties:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not cap else max(0, cap - len(records))
            if cap and remaining == 0:
                break
            try:
                batch = self.scrape_county(
                    state,
                    county,
                    row_limit=remaining or 0,
                    max_pages=max_pages,
                    skip_existing_urls=known,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    progress_cb=None,
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
                    progress_cb(len(records), cap or None)
                if cap and len(records) >= cap:
                    return records[:cap]
        return records[:cap] if cap else records

    def scrape(
        self,
        row_limit: int = 0,
        *,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[ProgressCallback] = None,
        record_cb: Optional[Callable[[Dict[str, Any], int], None]] = None,
    ) -> List[Dict[str, Any]]:
        """Walk states/counties until ``row_limit`` records are collected."""
        cap = int(row_limit or 0)
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        try:
            states = discover_states_from_homepage(self.client)
        except Exception:
            states = []
        for state in states:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not cap else max(0, cap - len(records))
            if cap and remaining == 0:
                break
            try:
                batch = self.scrape_state(
                    state,
                    row_limit=remaining or 0,
                    max_pages=1 if cap else 0,
                    skip_existing_urls=known,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    progress_cb=None,
                    record_cb=None,
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
                    progress_cb(len(records), cap or None)
                if cap and len(records) >= cap:
                    return records[:cap]
        return records[:cap] if cap else records
