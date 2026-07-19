"""Normalize RecentlyBooked human booking dates to ISO for Browse sorting.

RB rows stored ``booking_date`` like ``July 6, 2026 8:50 PM`` with empty
``arrest_date``. Browse orders by arrest/booking date DESC, so those rows
never appeared in the first page under multi-million DOC imports.

Usage (from repo root)::

    python scripts/backfill_rb_iso_dates.py
    python scripts/backfill_rb_iso_dates.py --db data/arrests.db
"""
from __future__ import annotations

import argparse
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scraper.recentlybooked.parse_util import normalize_booking_datetime  # noqa: E402

_ISO = re.compile(r"^\d{4}-\d{2}-\d{2}")


def _is_iso(val: object) -> bool:
    return bool(_ISO.match(str(val or "").strip()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default=str(ROOT / "data" / "arrests.db"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """
        SELECT id, booking_date, arrest_date, arrest_time
        FROM arrests
        WHERE source_system = 'recentlybooked'
        """
    ).fetchall()
    updated = 0
    skipped = 0
    for r in rows:
        booking = str(r["booking_date"] or "").strip()
        arrest = str(r["arrest_date"] or "").strip()
        if _is_iso(booking) and _is_iso(arrest):
            skipped += 1
            continue
        raw = booking or arrest
        parsed = normalize_booking_datetime(raw)
        day = parsed.get("booking_date") or parsed.get("arrest_date") or ""
        if not _is_iso(day):
            skipped += 1
            continue
        new_booking = day if not _is_iso(booking) else booking[:10]
        new_arrest = day if not _is_iso(arrest) else arrest[:10]
        new_time = parsed.get("arrest_time") or r["arrest_time"]
        if args.dry_run:
            updated += 1
            continue
        conn.execute(
            """
            UPDATE arrests
            SET booking_date = ?, arrest_date = ?, arrest_time = ?
            WHERE id = ?
            """,
            (new_booking, new_arrest, new_time, int(r["id"])),
        )
        updated += 1
    if not args.dry_run:
        conn.commit()
    conn.close()
    print(
        f"rows={len(rows)} updated={updated} skipped={skipped} dry={args.dry_run}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
