#!/usr/bin/env python3
"""Check identity safety in the public records archive.

Run after bulk scrapes. Use --repair to clear nuclear hits.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATES = (
    "alabama", "alaska", "arizona", "arkansas", "california",
    "colorado", "connecticut", "delaware", "florida", "georgia",
    "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas",
    "kentucky", "louisiana", "maine", "maryland", "massachusetts",
    "michigan", "minnesota", "mississippi", "missouri", "montana",
    "nebraska", "nevada", "new hampshire", "new jersey",
    "new mexico", "new york", "north carolina", "north dakota",
    "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island",
    "south carolina", "south dakota", "tennessee", "texas",
    "utah", "vermont", "virginia", "washington", "west virginia",
    "wisconsin", "wyoming", "district of columbia",
)


def connect(db: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    return conn


def state_stub_rows(conn: sqlite3.Connection, limit: int):
    ph = ",".join("?" for _ in STATES)
    sql = (
        "SELECT id, full_name, charge_description, source_system, state "
        "FROM arrests "
        f"WHERE LOWER(TRIM(COALESCE(charge_description, ''))) IN ({ph}) "
        "ORDER BY id DESC LIMIT ?"
    )
    return conn.execute(sql, (*STATES, int(limit))).fetchall()


def count_state_stubs(conn: sqlite3.Connection) -> int:
    ph = ",".join("?" for _ in STATES)
    sql = (
        "SELECT COUNT(*) c FROM arrests "
        f"WHERE LOWER(TRIM(COALESCE(charge_description,''))) IN ({ph})"
    )
    return int(conn.execute(sql, (*STATES,)).fetchone()["c"])


def missing_dob_sample(conn: sqlite3.Connection) -> int:
    sql = (
        "SELECT COUNT(*) c FROM (SELECT 1 FROM arrests "
        "WHERE date_of_birth IS NULL OR TRIM(date_of_birth) = '' LIMIT 10001)"
    )
    return int(conn.execute(sql).fetchone()["c"])


def repair_state_stubs(conn: sqlite3.Connection, limit: int) -> int:
    rows = state_stub_rows(conn, limit)
    if not rows:
        return 0
    ids = [int(r["id"]) for r in rows]
    chunk = 200
    n = 0
    for i in range(0, len(ids), chunk):
        part = ids[i:i + chunk]
        ph = ",".join("?" for _ in part)
        conn.execute(
            f"UPDATE arrests SET charge_description = NULL, "
            f"charge_category = 'unknown' WHERE id IN ({ph})",
            part,
        )
        n += len(part)
    conn.commit()
    return n


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", nargs="?", default="data/arrests.db")
    ap.add_argument("--limit", type=int, default=500)
    ap.add_argument("--repair", action="store_true")
    ap.add_argument("--show", type=int, default=10)
    args = ap.parse_args()
    conn = connect(args.db)
    try:
        stubs = count_state_stubs(conn)
        print(f"state-name charges: {stubs}")
        if stubs:
            for r in state_stub_rows(conn, args.show):
                d = dict(r)
                print(f"  id={d['id']} charge={d['charge_description']!r} "
                      f"name={d['full_name']!r} sys={d['source_system']}")
        dob = missing_dob_sample(conn)
        print(f"missing DOB (capped at 10001): {dob}")
        if args.repair:
            if stubs == 0:
                print("No nuclear hits. Nothing to repair.")
                return 0
            n = repair_state_stubs(conn, args.limit)
            print(f"Repaired {n} state-name charges (set to NULL).")
            left = count_state_stubs(conn)
            print(f"state-name charges left: {left}")
            return 0 if left == 0 else 2
        if stubs > 0:
            print("Nuclear hits found. Re-run with --repair.")
            return 2
        print("OK. No nuclear hits.")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
