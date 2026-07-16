"""Load-balanced county/state scrape across hosts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional, Set, Tuple

from .partition import partition_work_units
from .result import MultiSourceResult
from .types import CancelCheck, ProgressCallback, RecordCallback


class BalancedScrapeMixin:
    """Partition work units and scrape disjoint county sets in parallel."""

    def scrape_balanced(
        self,
        *,
        state: Optional[str] = None,
        county: Optional[str] = None,
        scrape_all: bool = False,
        row_limit: int = 0,
        workers_per_source: int = 2,
        skip_existing_urls: Optional[Set[str]] = None,
        with_photos: bool = True,
        cancel_check: Optional[CancelCheck] = None,
        record_cb: Optional[RecordCallback] = None,
        progress_cb: Optional[ProgressCallback] = None,
    ) -> MultiSourceResult:
        """
        Full scrape with work partitioned across hosts.

        - If multiple sources are selected, county units are round-robin assigned
          so each host scrapes a disjoint set of counties.
        - Identity index prevents detail fetches for people already seen on
          another host in this run.
        """
        result = MultiSourceResult()
        if skip_existing_urls:
            for u in skip_existing_urls:
                self.identity.add_url(u)
        wrapped, skipped_fn = self._wrap_record_cb(record_cb, skip_identity=True)

        # Single-county: pick the least-loaded (first available) host only,
        # unless user selected one source.
        if county and state and not scrape_all:
            sid = self.source_ids[0] if self.source_ids else None
            if not sid:
                return result
            try:
                n = self._scrape_geo(
                    sid,
                    state=state,
                    county=county,
                    scrape_all=False,
                    row_limit=row_limit,
                    workers=workers_per_source,
                    with_photos=with_photos,
                    cancel_check=cancel_check,
                    record_cb=wrapped,
                    progress_cb=progress_cb,
                )
                result.by_source[sid] = n
            except Exception as exc:
                result.errors[sid] = str(exc)
            result.skipped_identity = skipped_fn()
            return result

        # Build county work list from the first available catalog source.
        units = self._discover_work_units(state=state, scrape_all=scrape_all)
        if not units:
            # Catalog discovery failed or returned nothing. Fall back to each host
            # walking its own catalog so the run does not silently end at 0 work.
            def run_independent(sid: str) -> Tuple[str, int, Optional[str]]:
                try:
                    n = self._scrape_geo(
                        sid,
                        state=state if not scrape_all else None,
                        county=None,
                        scrape_all=bool(scrape_all),
                        row_limit=row_limit,
                        workers=workers_per_source,
                        with_photos=with_photos,
                        cancel_check=cancel_check,
                        record_cb=wrapped,
                        progress_cb=progress_cb,
                    )
                    return sid, n, None
                except Exception as exc:
                    return sid, 0, str(exc)

            if scrape_all or state:
                if progress_cb:
                    try:
                        progress_cb(
                            0,
                            None,
                            {
                                "label": (
                                    "multi-host · catalog empty — "
                                    "each source walks its own list"
                                )
                            },
                        )
                    except Exception:
                        pass
                with ThreadPoolExecutor(
                    max_workers=max(1, len(self.source_ids))
                ) as pool:
                    futs = [
                        pool.submit(run_independent, sid) for sid in self.source_ids
                    ]
                    for fut in as_completed(futs):
                        sid, n, err = fut.result()
                        result.by_source[sid] = n
                        if err:
                            result.errors[sid] = err
                result.skipped_identity = skipped_fn()
                return result
            result.errors["catalog"] = "No counties/states discovered for scrape."
            result.skipped_identity = skipped_fn()
            return result

        buckets = partition_work_units(units, self.source_ids)

        def run_bucket(
            sid: str, work: List[Tuple[str, str]]
        ) -> Tuple[str, int, Optional[str], Dict[str, str]]:
            total = 0
            local_errors: Dict[str, str] = {}
            try:
                for st, co in work:
                    if cancel_check and cancel_check():
                        break
                    remaining = 0 if not row_limit else max(0, row_limit - total)
                    if row_limit and remaining == 0:
                        break
                    try:
                        n = self._scrape_geo(
                            sid,
                            state=st,
                            county=co,
                            scrape_all=False,
                            row_limit=remaining or 0,
                            workers=workers_per_source,
                            with_photos=with_photos,
                            cancel_check=cancel_check,
                            record_cb=wrapped,
                            progress_cb=progress_cb,
                        )
                        total += n
                    except Exception as county_exc:
                        # Keep other counties running; surface the failure.
                        local_errors[f"{sid}:{st}/{co}"] = str(county_exc)
                        if progress_cb:
                            try:
                                progress_cb(
                                    total,
                                    None,
                                    {
                                        "source": sid,
                                        "state": st,
                                        "county": co,
                                        "label": (
                                            f"{sid} · {st}/{co} · error: {county_exc}"
                                        ),
                                    },
                                )
                            except Exception:
                                pass
                return sid, total, None, local_errors
            except Exception as exc:
                return sid, total, str(exc), local_errors

        with ThreadPoolExecutor(max_workers=max(1, len(buckets))) as pool:
            futs = [
                pool.submit(run_bucket, sid, work)
                for sid, work in buckets.items()
                if work
            ]
            if not futs:
                result.errors["partition"] = (
                    f"Discovered {len(units)} unit(s) but none were assigned to hosts."
                )
            for fut in as_completed(futs):
                sid, n, err, local_errs = fut.result()
                result.by_source[sid] = result.by_source.get(sid, 0) + n
                if err:
                    result.errors[sid] = err
                result.errors.update(local_errs or {})
        result.skipped_identity = skipped_fn()
        return result
