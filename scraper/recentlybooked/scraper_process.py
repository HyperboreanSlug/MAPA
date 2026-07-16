"""Record enrichment and parallel card/county processing for RecentlyBooked."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional

from ..charge_classifications import classify_record
from .archive_html import archive_html
from .client import RecentlyBookedClient
from .locked_set import LockedURLSet
from .parse import parse_detail
from .photos import download_photo

CancelCheck = Optional[Any]
ProgressCallback = Optional[Any]
RecordCallback = Optional[Any]


class RecentlyBookedProcessMixin:
    """_process_record and parallel helpers."""

    def _process_record(
        self,
        record: Dict[str, Any],
        *,
        import_details: bool,
        with_photos: bool,
        with_html: bool,
        client: Optional[RecentlyBookedClient] = None,
    ) -> Dict[str, Any]:
        http = client or self.client
        try:
            if import_details or with_html:
                detail_html = http.get(str(record["source_url"]))
                if import_details:
                    parsed = parse_detail(detail_html, str(record["source_url"]))
                    # Prefer non-empty detail values; do not wipe card photo_url.
                    for key, val in parsed.items():
                        if val is None or val == "":
                            continue
                        record[key] = val
                if with_html:
                    html_path = archive_html(detail_html, record)
                    if html_path:
                        record["html_path"] = str(html_path)
            if with_photos:
                photo_path = download_photo(record, http)
                if photo_path:
                    record["photo_path"] = str(photo_path)
            classify_record(record)
        except Exception as exc:
            record["scrape_error"] = f"{type(exc).__name__}: {exc}"
        return record

    def _process_cards_parallel(
        self,
        cards: List[Dict[str, Any]],
        *,
        workers: int,
        with_photos: bool,
        with_html: bool,
        cancel_check,
        progress_cb,
        record_cb,
        records: List[Dict[str, Any]],
        scrape_loc: str = "",
        progress_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        from ..client_pool import ClientPool

        lock = threading.Lock()
        workers = max(1, int(workers or 1))
        # One client per worker: delay is paced on that client's timeline
        # (per-thread), not as a global inter-request gate.
        pool_clients = ClientPool(
            lambda: RecentlyBookedClient(delay=self.delay), workers
        )

        def job(card: Dict[str, Any]) -> Dict[str, Any]:
            if self._cancelled(cancel_check):
                return dict(card)
            http = pool_clients.borrow()
            try:
                done = self._process_record(
                    dict(card),
                    import_details=True,
                    with_photos=with_photos,
                    with_html=with_html,
                    client=http,
                )
                if scrape_loc:
                    done["_scrape_loc"] = scrape_loc
                return done
            finally:
                pool_clients.release(http)

        try:
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(job, card) for card in cards]
                for fut in as_completed(futures):
                    if self._cancelled(cancel_check):
                        for pending in futures:
                            pending.cancel()
                        break
                    try:
                        done = fut.result()
                    except Exception as exc:
                        done = {"scrape_error": f"{type(exc).__name__}: {exc}"}
                    with lock:
                        records.append(done)
                        count = len(records)
                    self._emit(record_cb, done, count)
                    self._report(progress_cb, count, progress_context)
        finally:
            pool_clients.close()

    def _scrape_counties_parallel(
        self,
        counties: List[tuple[str, str]],
        *,
        workers: int,
        max_pages: int,
        known_urls: LockedURLSet,
        with_photos: bool,
        with_html: bool,
        cancel_check,
        progress_cb,
        record_cb,
    ) -> List[Dict[str, Any]]:
        from .scraper import RecentlyBookedScraper

        records: List[Dict[str, Any]] = []
        total = 0
        lock = threading.Lock()

        def forward(rec: Dict[str, Any], _n: int) -> None:
            nonlocal total
            with lock:
                total += 1
                count = total
                records.append(rec)
            self._emit(record_cb, rec, count)
            self._report(progress_cb, count)

        def job(pair: tuple[str, str]) -> None:
            if self._cancelled(cancel_check):
                return
            state, county = pair
            loc = self._loc_label(
                state=state, county=county, source="recentlybooked"
            )
            self._report(
                progress_cb,
                total,
                {"state": state, "county": county, "label": loc},
            )
            with RecentlyBookedScraper(delay=self.delay) as local:
                local.scrape_county(
                    state, county, max_pages=max_pages,
                    skip_existing_urls=known_urls, with_photos=with_photos,
                    with_html=with_html, cancel_check=cancel_check,
                    progress_cb=progress_cb, record_cb=forward, workers=1,
                )

        if not counties:
            self._report(
                progress_cb,
                0,
                {"label": "recentlybooked · 0 counties to scrape"},
            )
            return records

        errors: List[str] = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(job, pair): pair for pair in counties}
            for fut in as_completed(futures):
                if self._cancelled(cancel_check):
                    for pending in futures:
                        pending.cancel()
                    break
                pair = futures[fut]
                try:
                    fut.result()
                except Exception as exc:
                    st, co = pair
                    msg = f"{st}/{co}: {type(exc).__name__}: {exc}"
                    errors.append(msg)
                    self._report(
                        progress_cb,
                        total,
                        {
                            "state": st,
                            "county": co,
                            "source": "recentlybooked",
                            "label": f"recentlybooked · {st}/{co} · error: {exc}",
                        },
                    )
        if errors and not records and not self._cancelled(cancel_check):
            # Surface total failure so the GUI does not show a silent "done: 0".
            raise RuntimeError(
                "RecentlyBooked county scrape failed: " + "; ".join(errors[:5])
            )
        return records
