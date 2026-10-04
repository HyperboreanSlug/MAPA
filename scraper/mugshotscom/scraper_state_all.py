"""Scrape mugshots.com state plus full site. Uses county mixin."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .catalog import discover_counties_for_state, discover_states_from_site


class MugshotsComStateAllMixin:
    def scrape_state(
        self, state: str, *, row_limit: int = 0, max_pages: int = 0,
        skip_existing_urls=None, with_photos: bool = True, cancel_check=None,
        progress_cb=None, record_cb=None, workers: int = 1,
    ) -> List[Dict[str, Any]]:
        known = set(skip_existing_urls or ())
        records: List[Dict[str, Any]] = []
        try:
            counties = discover_counties_for_state(self.client, state)
        except Exception as exc:
            counties = []
            if progress_cb:
                try:
                    progress_cb(
                        0,
                        None,
                        {
                            "state": state,
                            "source": "mugshotscom",
                            "label": f"mugshotscom · {state} · county list failed: {exc}",
                        },
                    )
                except Exception:
                    pass
        if not counties and progress_cb:
            try:
                progress_cb(
                    0,
                    None,
                    {
                        "state": state,
                        "source": "mugshotscom",
                        "label": f"mugshotscom · {state} · 0 counties found",
                    },
                )
            except Exception:
                pass

        def _forward(done: Dict[str, Any], _n: int) -> None:
            records.append(done)
            url = str(done.get("source_url") or "")
            if url:
                known.add(url)
            if record_cb:
                record_cb(done, len(records))
            if progress_cb:
                try:
                    progress_cb(len(records), row_limit or None)
                except TypeError:
                    progress_cb(len(records), None)

        # max_pages=0 means unlimited — never coerce to 1 (that only scraped p1).
        pages = int(max_pages or 0)
        for county in counties:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not row_limit else max(0, row_limit - len(records))
            if row_limit and remaining == 0:
                break
            self.scrape_county(
                state,
                county,
                row_limit=remaining or 0,
                max_pages=pages,
                skip_existing_urls=known,
                with_photos=with_photos,
                cancel_check=cancel_check,
                progress_cb=progress_cb,
                record_cb=_forward,
                workers=workers,
            )
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
        except Exception as exc:
            states = []
            if progress_cb:
                try:
                    progress_cb(
                        0,
                        None,
                        {
                            "source": "mugshotscom",
                            "label": f"mugshotscom · state list failed: {exc}",
                        },
                    )
                except Exception:
                    pass
        if not states and progress_cb:
            try:
                progress_cb(
                    0,
                    None,
                    {"source": "mugshotscom", "label": "mugshotscom · 0 states found"},
                )
            except Exception:
                pass

        def _forward(done: Dict[str, Any], _n: int) -> None:
            records.append(done)
            url = str(done.get("source_url") or "")
            if url:
                known.add(url)
            if record_cb:
                record_cb(done, len(records))
            if progress_cb:
                try:
                    progress_cb(len(records), row_limit or None)
                except TypeError:
                    progress_cb(len(records), None)

        for state in states:
            if self._cancelled(cancel_check):
                break
            remaining = 0 if not row_limit else max(0, row_limit - len(records))
            if row_limit and remaining == 0:
                break
            try:
                # Unlimited pages for full scrape; cap to 1 page only when sampling.
                pages = 1 if row_limit else 0
                self.scrape_state(
                    state,
                    row_limit=remaining or 0,
                    max_pages=pages,
                    skip_existing_urls=known,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    progress_cb=progress_cb,
                    record_cb=_forward,
                    workers=workers,
                )
            except Exception as exc:
                if progress_cb:
                    try:
                        progress_cb(
                            len(records),
                            None,
                            {
                                "state": state,
                                "source": "mugshotscom",
                                "label": f"mugshotscom · {state} · error: {exc}",
                            },
                        )
                    except Exception:
                        pass
                continue
            if row_limit and len(records) >= row_limit:
                return records[:row_limit]
        return records[:row_limit] if row_limit else records
