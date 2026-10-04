"""Scrape one mugshots.com county. Page loop with dedupe."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set

from .catalog import (
    BASE_URL,
    county_page_url,
    detail_urls_from_listing,
    state_slug_from_code,
)
from .locked_set import LockedURLSet
from .parse import parse_listing_cards


class MugshotsComOneCountyMixin:
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
        list_fail_streak = 0

        while not max_pages or page <= max_pages:
            if self._cancelled(cancel_check):
                break
            if row_limit and len(records) >= row_limit:
                break
            list_url = county_page_url(state, county, page)
            if list_url in visited_pages:
                break
            visited_pages.add(list_url)
            loc = f"mugshotscom · {state}/{county} · p{page}"
            if progress_cb:
                try:
                    progress_cb(
                        len(records),
                        None,
                        {
                            "state": state,
                            "county": county,
                            "page": page,
                            "source": "mugshotscom",
                            "label": loc,
                        },
                    )
                except TypeError:
                    progress_cb(len(records), None)
            try:
                html = self.client.get(
                    list_url,
                    referer=f"{BASE_URL}/US-States/{state_slug_from_code(state)}/",
                )
            except Exception as exc:
                # Transient list errors used to end the county with no log.
                if progress_cb:
                    try:
                        progress_cb(
                            len(records),
                            None,
                            {
                                "state": state,
                                "county": county,
                                "page": page,
                                "source": "mugshotscom",
                                "label": f"{loc} · list error: {exc}",
                            },
                        )
                    except TypeError:
                        progress_cb(len(records), None)
                    except Exception:
                        pass
                # Retry next page once after a blip; two consecutive failures end county.
                list_fail_streak += 1
                if list_fail_streak >= 2:
                    break
                page += 1
                continue
            list_fail_streak = 0
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
                card["_scrape_loc"] = loc
                batch.append(card)
            # Keep paging past already-known listing pages until empty/repeat.
            if not batch:
                page += 1
                continue

            if workers == 1:
                for card in batch:
                    if self._cancelled(cancel_check):
                        return records
                    if row_limit and len(records) >= row_limit:
                        return records
                    done = self._enrich(card, with_photos=with_photos)
                    records.append(done)
                    if record_cb:
                        record_cb(done, len(records))
                    if progress_cb:
                        progress_cb(len(records), row_limit or None)
            else:
                self._enrich_batch_parallel(
                    batch,
                    workers=workers,
                    with_photos=with_photos,
                    records=records,
                    lock=lock,
                    row_limit=row_limit,
                    cancel_check=cancel_check,
                    record_cb=record_cb,
                    progress_cb=progress_cb,
                )
            page += 1
        return records[:row_limit] if row_limit else records

