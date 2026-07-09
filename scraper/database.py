"""SQLite storage for public arrest/booking records."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timezone

DEFAULT_DB_PATH = "data/arrests.db"
SCHEMA_VERSION = 2

_ARREST_COLUMNS = (
    "first_name", "middle_name", "last_name", "full_name",
    "race", "ethnicity", "sex", "gender", "age", "date_of_birth",
    "arrest_date", "arrest_time", "booking_date", "release_date",
    "agency", "jurisdiction", "state", "county", "city", "address",
    "latitude", "longitude",
    "charge_description", "charge_group", "charge_level", "charge_class",
    "charge_category",
    "statute", "case_number", "booking_id",
    "source_id", "source_url", "source_system", "raw_json",
    "likely_ethnicity", "name_confidence", "flags",
)

_INSERT_SQL = (
    "INSERT INTO arrests ("
    + ", ".join(_ARREST_COLUMNS)
    + ") VALUES ("
    + ", ".join("?" * len(_ARREST_COLUMNS))
    + ")"
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _escape_like(value: str) -> str:
    return (
        (value or "")
        .replace("\\", "\\\\")
        .replace("%", "\\%")
        .replace("_", "\\_")
    )


def _to_tuple(record: Dict[str, Any]) -> tuple:
    return tuple(record.get(c) for c in _ARREST_COLUMNS)


class Database:
    def __init__(self, db_path: Optional[str] = None):
        if db_path == ":memory:":
            self.db_path = Path(":memory:")
            self._conn = sqlite3.connect(":memory:")
        else:
            self.db_path = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=60000")
        self._init_schema()

    def _init_schema(self) -> None:
        c = self._conn.cursor()
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TEXT NOT NULL
            )
            """
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS arrests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                first_name TEXT,
                middle_name TEXT,
                last_name TEXT,
                full_name TEXT,
                race TEXT,
                ethnicity TEXT,
                sex TEXT,
                gender TEXT,
                age INTEGER,
                date_of_birth TEXT,
                arrest_date TEXT,
                arrest_time TEXT,
                booking_date TEXT,
                release_date TEXT,
                agency TEXT,
                jurisdiction TEXT,
                state TEXT,
                county TEXT,
                city TEXT,
                address TEXT,
                latitude REAL,
                longitude REAL,
                charge_description TEXT,
                charge_group TEXT,
                charge_level TEXT,
                charge_class TEXT,
                charge_category TEXT,
                statute TEXT,
                case_number TEXT,
                booking_id TEXT,
                source_id TEXT,
                source_url TEXT,
                source_system TEXT,
                raw_json TEXT,
                likely_ethnicity TEXT,
                name_confidence REAL,
                flags TEXT,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        # Migrations for existing DBs
        cols = {r[1] for r in c.execute("PRAGMA table_info(arrests)")}
        if "charge_category" not in cols:
            c.execute("ALTER TABLE arrests ADD COLUMN charge_category TEXT")
        for idx, col in (
            ("idx_arrests_last_name", "last_name"),
            ("idx_arrests_race", "race"),
            ("idx_arrests_state", "state"),
            ("idx_arrests_source_url", "source_url"),
            ("idx_arrests_source_system", "source_system"),
            ("idx_arrests_arrest_date", "arrest_date"),
            ("idx_arrests_charge", "charge_description"),
            ("idx_arrests_charge_category", "charge_category"),
        ):
            if col == "charge_category" and "charge_category" not in cols and col not in {
                r[1] for r in c.execute("PRAGMA table_info(arrests)")
            }:
                continue
            c.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON arrests({col})")
        row = c.execute("SELECT MAX(version) FROM schema_version").fetchone()
        ver = (row[0] or 0) if row else 0
        if ver < SCHEMA_VERSION:
            c.execute(
                "INSERT INTO schema_version (version, applied_at) VALUES (?, ?)",
                (SCHEMA_VERSION, _utc_now_iso()),
            )
        self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass

    def get_total_count(self) -> int:
        r = self._conn.execute("SELECT COUNT(*) FROM arrests").fetchone()
        return int(r[0]) if r else 0

    def existing_source_urls(self) -> set:
        rows = self._conn.execute(
            "SELECT source_url FROM arrests "
            "WHERE source_url IS NOT NULL AND TRIM(source_url) != ''"
        ).fetchall()
        return {str(r[0]).strip() for r in rows if r and r[0]}

    def insert_arrest(self, record: Dict[str, Any]) -> int:
        cur = self._conn.cursor()
        cur.execute(_INSERT_SQL, _to_tuple(record))
        self._conn.commit()
        return int(cur.lastrowid)

    def insert_arrests_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        cur = self._conn.cursor()
        cur.executemany(_INSERT_SQL, [_to_tuple(r) for r in records])
        self._conn.commit()
        n = cur.rowcount
        return n if n is not None and n >= 0 else len(records)

    def import_records(
        self,
        records: List[Dict[str, Any]],
        *,
        skip_existing_urls: bool = True,
    ) -> Dict[str, int]:
        from .charge_classifications import classify_record

        prepared = [dict(r) for r in (records or []) if isinstance(r, dict)]
        for rec in prepared:
            classify_record(rec)
        total = len(prepared)
        skipped = 0
        if skip_existing_urls:
            existing = self.existing_source_urls()
            kept = []
            for rec in prepared:
                url = (rec.get("source_url") or rec.get("source_id") or "").strip()
                if url and url in existing:
                    skipped += 1
                    continue
                if url:
                    existing.add(url)
                kept.append(rec)
            prepared = kept
        imported = self.insert_arrests_batch(prepared) if prepared else 0
        return {"imported": imported, "skipped": skipped, "total_rows": total}

    def reclassify_charges(self) -> int:
        """Backfill charge_category for all rows. Returns rows updated."""
        from .charge_classifications import classify_charge

        rows = self._conn.execute(
            "SELECT id, charge_description, charge_group, charge_level, "
            "charge_class, statute FROM arrests"
        ).fetchall()
        n = 0
        for row in rows:
            d = dict(row)
            cat = classify_charge(d)
            self._conn.execute(
                "UPDATE arrests SET charge_category = ? WHERE id = ?",
                (cat, d["id"]),
            )
            n += 1
        self._conn.commit()
        return n

    def search_by_name(
        self,
        name: str,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        esc = _escape_like(name or "")
        term = f"%{esc}%"
        q += (
            " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
            "OR last_name LIKE ? ESCAPE '\\')"
        )
        params.extend([term, term, term])
        if state and state.upper() != "ALL":
            q += " AND UPPER(COALESCE(state, '')) = UPPER(?)"
            params.append(state)
        if race:
            q += " AND UPPER(COALESCE(race, '')) = UPPER(?)"
            params.append(race)
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params.append(charge_category)
        q += " ORDER BY last_name ASC, first_name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def search_records(
        self,
        *,
        name: Optional[str] = None,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Flexible search; name optional when filtering by charge only."""
        limit = max(0, int(limit))
        offset = max(0, int(offset))
        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        if name and str(name).strip():
            esc = _escape_like(str(name).strip())
            term = f"%{esc}%"
            q += (
                " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
                "OR last_name LIKE ? ESCAPE '\\')"
            )
            params.extend([term, term, term])
        if state and state.upper() != "ALL":
            q += " AND UPPER(COALESCE(state, '')) = UPPER(?)"
            params.append(state)
        if race:
            q += " AND UPPER(COALESCE(race, '')) = UPPER(?)"
            params.append(race)
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            q += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params.append(charge_category)
        q += " ORDER BY arrest_date DESC, last_name ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])
        return [dict(r) for r in self._conn.execute(q, params).fetchall()]

    def get_charge_category_distribution(self) -> List[Dict[str, Any]]:
        from .charge_classifications import category_label

        rows = self._conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(charge_category), ''), 'unknown') AS cat,
                   COUNT(*) AS count
            FROM arrests
            GROUP BY cat
            ORDER BY count DESC
            """
        ).fetchall()
        return [
            {
                "category": r["cat"],
                "label": category_label(r["cat"]),
                "count": int(r["count"] or 0),
            }
            for r in rows
        ]

    def iter_arrests(
        self,
        limit: Optional[int] = None,
        offset: int = 0,
        *,
        newest_first: bool = False,
        named_only: bool = False,
        charge_category: Optional[str] = None,
    ):
        offset = max(0, int(offset or 0))
        order = "DESC" if newest_first else "ASC"
        where = "WHERE 1=1"
        params_list: List[Any] = []
        if named_only:
            where += (
                " AND ("
                "(last_name IS NOT NULL AND TRIM(last_name) != '') "
                "OR (full_name IS NOT NULL AND TRIM(full_name) != '')"
                ")"
            )
        if charge_category and str(charge_category).lower() not in ("all", "", "*"):
            where += " AND LOWER(COALESCE(charge_category, '')) = LOWER(?)"
            params_list.append(charge_category)
        if limit is None or int(limit) <= 0:
            sql = f"SELECT * FROM arrests {where} ORDER BY id {order}"
            params: tuple = tuple(params_list)
            if offset:
                sql += " LIMIT -1 OFFSET ?"
                params = tuple(params_list) + (offset,)
        else:
            sql = f"SELECT * FROM arrests {where} ORDER BY id {order} LIMIT ? OFFSET ?"
            params = tuple(params_list) + (int(limit), offset)
        for row in self._conn.execute(sql, params):
            yield dict(row)

    def get_integrity_report(self) -> Dict[str, Any]:
        def _pct(n: int, d: int) -> float:
            return round(100.0 * n / d, 1) if d else 0.0

        total = self.get_total_count()
        row = self._conn.execute(
            """
            SELECT
              SUM(CASE WHEN race IS NOT NULL AND TRIM(race) != '' THEN 1 ELSE 0 END) AS with_race,
              SUM(CASE WHEN last_name IS NOT NULL AND TRIM(last_name) != '' THEN 1 ELSE 0 END) AS with_name,
              SUM(CASE WHEN charge_description IS NOT NULL AND TRIM(charge_description) != '' THEN 1 ELSE 0 END) AS with_charge,
              SUM(CASE WHEN arrest_date IS NOT NULL AND TRIM(arrest_date) != '' THEN 1 ELSE 0 END) AS with_date,
              SUM(CASE WHEN source_url IS NOT NULL AND TRIM(source_url) != '' THEN 1 ELSE 0 END) AS with_url
            FROM arrests
            """
        ).fetchone()
        overall = {
            "total": total,
            "with_race": int(row["with_race"] or 0) if row else 0,
            "with_name": int(row["with_name"] or 0) if row else 0,
            "with_charge": int(row["with_charge"] or 0) if row else 0,
            "with_date": int(row["with_date"] or 0) if row else 0,
            "with_url": int(row["with_url"] or 0) if row else 0,
        }
        for k in ("race", "name", "charge", "date", "url"):
            overall[f"pct_{k}"] = _pct(overall[f"with_{k}"], total)

        by_state = []
        for r in self._conn.execute(
            """
            SELECT COALESCE(NULLIF(TRIM(UPPER(state)), ''), 'UNK') AS st,
                   COUNT(*) AS total,
                   SUM(CASE WHEN race IS NOT NULL AND TRIM(race) != '' THEN 1 ELSE 0 END) AS with_race,
                   SUM(CASE WHEN last_name IS NOT NULL AND TRIM(last_name) != '' THEN 1 ELSE 0 END) AS with_name
            FROM arrests GROUP BY st ORDER BY total DESC
            """
        ):
            t = int(r["total"] or 0)
            by_state.append({
                "state": r["st"] or "UNK",
                "total": t,
                "with_race": int(r["with_race"] or 0),
                "with_name": int(r["with_name"] or 0),
                "pct_race": _pct(int(r["with_race"] or 0), t),
                "pct_name": _pct(int(r["with_name"] or 0), t),
            })
        return {"overall": overall, "by_state": by_state}

    def get_race_distribution(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT race, COUNT(*) as count FROM arrests GROUP BY race ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_state_distribution(self) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT state, COUNT(*) as count FROM arrests GROUP BY state ORDER BY count DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def export_to_csv(self, output_path: str, filters: Optional[Dict[str, Any]] = None) -> int:
        import csv as csv_module

        q = "SELECT * FROM arrests WHERE 1=1"
        params: List[Any] = []
        if filters:
            if filters.get("state") and str(filters["state"]).upper() != "ALL":
                q += " AND UPPER(COALESCE(state,'')) = UPPER(?)"
                params.append(filters["state"])
            if filters.get("race"):
                q += " AND UPPER(COALESCE(race,'')) = UPPER(?)"
                params.append(filters["race"])
            if filters.get("name"):
                term = f"%{_escape_like(str(filters['name']))}%"
                q += (
                    " AND (full_name LIKE ? ESCAPE '\\' OR first_name LIKE ? ESCAPE '\\' "
                    "OR last_name LIKE ? ESCAPE '\\')"
                )
                params.extend([term, term, term])
        rows = self._conn.execute(q, params).fetchall()
        fieldnames = ["id", *_ARREST_COLUMNS, "scraped_at"]
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv_module.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            w.writeheader()
            for row in rows:
                w.writerow(dict(row))
        return len(rows)

    # ---- Duplicates (safe source_url) ----

    def find_duplicate_groups(self, strategy: str = "source_url") -> List[Dict[str, Any]]:
        if strategy != "source_url":
            raise ValueError("Only source_url strategy implemented in v0.1")
        rows = self._conn.execute(
            """
            SELECT TRIM(source_url) AS dup_key, COUNT(*) AS cnt, GROUP_CONCAT(id) AS id_list
            FROM arrests
            WHERE source_url IS NOT NULL AND TRIM(source_url) != ''
            GROUP BY TRIM(source_url)
            HAVING COUNT(*) > 1
            ORDER BY cnt DESC
            """
        ).fetchall()
        groups = []
        for r in rows:
            ids = [int(x) for x in str(r["id_list"] or "").split(",") if x.strip().isdigit()]
            if len(ids) < 2:
                continue
            groups.append({
                "key": r["dup_key"],
                "count": len(ids),
                "ids": ids,
                "keep_id": min(ids),
                "remove_ids": sorted(ids)[1:],
            })
        return groups

    def remove_duplicates(self, strategy: str = "source_url", *, dry_run: bool = False) -> Dict[str, Any]:
        groups = self.find_duplicate_groups(strategy)
        deleted = []
        for g in groups:
            for rid in g["remove_ids"]:
                if not dry_run:
                    self._conn.execute("DELETE FROM arrests WHERE id = ?", (rid,))
                deleted.append(rid)
        if not dry_run and deleted:
            self._conn.commit()
        return {
            "strategy": strategy,
            "dry_run": dry_run,
            "groups": len(groups),
            "deleted": len(deleted),
        }

    @classmethod
    def create_in_memory(cls) -> "Database":
        return cls(db_path=":memory:")


_db_singleton: Optional[Database] = None


def get_database(db_path: Optional[str] = None) -> Database:
    global _db_singleton
    if db_path is not None:
        return Database(db_path)
    if _db_singleton is None:
        _db_singleton = Database()
    return _db_singleton
