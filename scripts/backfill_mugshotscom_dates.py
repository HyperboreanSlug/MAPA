"""Backfill arrest/booking dates for mugshots.com rows missing both.

Re-fetches detail pages and applies parse_detail Date-added fallback
(``div.item-date`` → arrest_date + booking_date). Also fills empty DOB /
name parts when the reparse provides them.

Usage:
  python scripts/backfill_mugshotscom_dates.py
  python scripts/backfill_mugshotscom_dates.py --dry-run --limit 20
  python scripts/backfill_mugshotscom_dates.py --workers 6 --delay 0.5
"""
from __future__ import annotations

import argparse
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.client_pool import ClientPool  # noqa: E402
from scraper.database import get_database  # noqa: E402
from scraper.mugshotscom.client import MugshotsComClient  # noqa: E402
from scraper.mugshotscom.parse_detail import parse_detail  # noqa: E402

_MISSING = """
SELECT id, source_url
FROM arrests
WHERE source_system = 'mugshotscom'
  AND source_url IS NOT NULL AND TRIM(source_url) != ''
  AND (arrest_date IS NULL OR TRIM(arrest_date) = '')
  AND (booking_date IS NULL OR TRIM(booking_date) = '')
ORDER BY id
"""


def _empty(v: Any) -> bool:
    return v is None or (isinstance(v, str) and not v.strip())


def _work(
    row_id: int,
    url: str,
    client: MugshotsComClient,
) -> Tuple[int, str, Optional[Dict[str, Any]]]:
    try:
        html = client.get(url)
        rec = parse_detail(html, url)
    except Exception as exc:
        return row_id, f"error:{type(exc).__name__}: {exc}", None
    date = rec.get("arrest_date") or rec.get("booking_date")
    if not date:
        return row_id, "no_date", None
    fields: Dict[str, Any] = {
        "arrest_date": rec.get("arrest_date") or date,
        "booking_date": rec.get("booking_date") or date,
    }
    for k in (
        "date_of_birth",
        "first_name",
        "middle_name",
        "last_name",
        "full_name",
    ):
        if rec.get(k):
            fields[k] = rec[k]
    if rec.get("raw_json"):
        fields["raw_json"] = rec["raw_json"]
    return row_id, "ok", fields


def backfill(
    *,
    dry_run: bool = False,
    limit: int = 0,
    workers: int = 4,
    delay: float = 0.5,
) -> Dict[str, int]:
    db = get_database()
    rows = db._conn.execute(_MISSING).fetchall()
    if limit and limit > 0:
        rows = rows[:limit]
    stats = {"total": len(rows), "updated": 0, "no_date": 0, "errors": 0}
    if not rows:
        return stats

    lock = threading.Lock()
    done = 0
    pool = ClientPool(lambda: MugshotsComClient(delay=delay), max(1, workers))

    def task(r) -> Tuple[int, str, Optional[Dict[str, Any]]]:
        http = pool.borrow()
        try:
            return _work(int(r["id"]), str(r["source_url"]), http)
        finally:
            pool.release(http)

    try:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
            futs = [ex.submit(task, r) for r in rows]
            for fut in as_completed(futs):
                row_id, status, fields = fut.result()
                with lock:
                    done += 1
                    n = done
                    if status == "ok" and fields:
                        stats["updated"] += 1
                        if not dry_run:
                            # Only fill empty name/DOB columns.
                            cur = db._conn.execute(
                                "SELECT date_of_birth, first_name, middle_name, "
                                "last_name, full_name, raw_json FROM arrests WHERE id=?",
                                (row_id,),
                            ).fetchone()
                            patch = {
                                "arrest_date": fields["arrest_date"],
                                "booking_date": fields["booking_date"],
                            }
                            if cur:
                                for k in (
                                    "date_of_birth",
                                    "first_name",
                                    "middle_name",
                                    "last_name",
                                    "full_name",
                                    "raw_json",
                                ):
                                    if k in fields and _empty(cur[k]):
                                        patch[k] = fields[k]
                            db.update_arrest(row_id, patch)
                    elif status == "no_date":
                        stats["no_date"] += 1
                    else:
                        stats["errors"] += 1
                        if stats["errors"] <= 8:
                            print(f"  id={row_id} {status}", flush=True)
                    if n % 50 == 0 or n == stats["total"]:
                        print(
                            f"  {n}/{stats['total']} updated={stats['updated']} "
                            f"no_date={stats['no_date']} err={stats['errors']}",
                            flush=True,
                        )
    finally:
        pool.close()
    return stats


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--delay", type=float, default=0.5)
    args = p.parse_args()
    print(
        f"Backfill mugshots.com dates "
        f"(workers={args.workers} delay={args.delay} "
        f"dry_run={args.dry_run} limit={args.limit or 'all'})",
        flush=True,
    )
    stats = backfill(
        dry_run=args.dry_run,
        limit=args.limit,
        workers=args.workers,
        delay=args.delay,
    )
    print(
        f"Done: total={stats['total']} updated={stats['updated']} "
        f"no_date={stats['no_date']} errors={stats['errors']}"
        + (" (dry-run)" if args.dry_run else ""),
        flush=True,
    )


if __name__ == "__main__":
    main()
