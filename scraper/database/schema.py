"""Schema init, connection, and core Database helpers."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional, Set

from scraper.database.constants import (
    DEFAULT_DB_PATH,
    SCHEMA_VERSION,
    _utc_now_iso,
)


class SchemaMixin:
    """Connection + schema migrations."""

    def __init__(self, db_path: Optional[str] = None):
        # check_same_thread=False: multi-thread scrapes import under an
        # application lock (GUI) or from a single importer thread (CLI).
        if db_path == ":memory:":
            self.db_path = Path(":memory:")
            self._conn = sqlite3.connect(
                ":memory:", check_same_thread=False
            )
        else:
            self.db_path = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(
                str(self.db_path), check_same_thread=False
            )
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
                photo_url TEXT,
                photo_path TEXT,
                html_path TEXT,
                hair TEXT,
                eyes TEXT,
                height TEXT,
                weight TEXT,
                scraped_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cols = {r[1] for r in c.execute("PRAGMA table_info(arrests)")}
        for col, typ in (
            ("charge_category", "TEXT"),
            ("photo_url", "TEXT"),
            ("photo_path", "TEXT"),
            ("html_path", "TEXT"),
            ("hair", "TEXT"),
            ("eyes", "TEXT"),
            ("height", "TEXT"),
            ("weight", "TEXT"),
        ):
            if col not in cols:
                c.execute(f"ALTER TABLE arrests ADD COLUMN {col} {typ}")
        for idx, col in (
            ("idx_arrests_last_name", "last_name"),
            ("idx_arrests_race", "race"),
            ("idx_arrests_state", "state"),
            ("idx_arrests_source_url", "source_url"),
            ("idx_arrests_source_system", "source_system"),
            ("idx_arrests_arrest_date", "arrest_date"),
            ("idx_arrests_charge", "charge_description"),
            ("idx_arrests_charge_category", "charge_category"),
            ("idx_arrests_photo", "photo_path"),
            ("idx_arrests_html", "html_path"),
        ):
            c.execute(f"CREATE INDEX IF NOT EXISTS {idx} ON arrests({col})")
        # deepface_scans (arrest_id)
        if hasattr(self, "_ensure_deepface_scans_table"):
            self._ensure_deepface_scans_table(c)
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

    def checkpoint(self) -> None:
        try:
            self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except Exception:
            pass

    def backup_to(self, dest: Path, *, verify: bool = True) -> None:
        dest = Path(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(dest.suffix + ".tmp")
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        dst = sqlite3.connect(str(tmp))
        try:
            self._conn.backup(dst)
            if verify:
                row = dst.execute("PRAGMA integrity_check").fetchone()
                if not row or str(row[0]).lower() != "ok":
                    raise RuntimeError(
                        f"Backup integrity_check failed: {row[0] if row else 'unknown'}"
                    )
        finally:
            dst.close()
        tmp.replace(dest)

    def get_total_count(self) -> int:
        r = self._conn.execute("SELECT COUNT(*) FROM arrests").fetchone()
        return int(r[0]) if r else 0

    def existing_source_urls(self) -> Set[str]:
        rows = self._conn.execute(
            "SELECT source_url FROM arrests "
            "WHERE source_url IS NOT NULL AND TRIM(source_url) != ''"
        ).fetchall()
        return {str(r[0]).strip() for r in rows if r and r[0]}

    def get_arrest_by_id(self, row_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM arrests WHERE id = ?", (int(row_id),)
        ).fetchone()
        return dict(row) if row else None

    # Alias used by DeepFace review UI adapted from SOR
    def get_offender_by_id(self, row_id: int) -> Optional[Dict[str, Any]]:
        return self.get_arrest_by_id(row_id)
