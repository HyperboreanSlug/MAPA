"""Cross-source identity keys and thread-safe claim index."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Set


def identity_keys_for_record(record: Dict[str, Any]) -> List[str]:
    """Build strong identity keys. Bind weak keys to name."""
    from scraper.database.dedupe import DedupeMixin

    keys: List[str] = []
    name = DedupeMixin.normalize_arrest_name(record)
    dob = DedupeMixin.dob_match_key(record)
    state = str(record.get("state") or "").strip().upper()
    if name and dob:
        keys.append(f"name_dob:{name}|{dob}")
        if state:
            keys.append(f"name_dob_st:{name}|{dob}|{state}")
    # Use booking date only with name. Drop it when DOB exists.
    bdate = str(record.get("booking_date") or record.get("arrest_date") or "").strip()[:10]
    if name and bdate and not dob:
        keys.append(f"name_bdate:{name}|{bdate}|{state}")
    # Bind booking ID to name. Stop merges across names.
    booking_id = str(record.get("booking_id") or "").strip().casefold()
    if booking_id and state and name:
        keys.append(f"booking:{state}|{booking_id}|{name}")
    # Bind photo token to name. Stop merges across names.
    kind, val = DedupeMixin.photo_identity_key(record)
    if kind != "none" and val and name:
        keys.append(f"photo:{kind}:{val}|{name}")
    return keys


class IdentityIndex:
    """Thread-safe identity set for cross-source duplicate suppression mid-scrape."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._keys: Set[str] = set()
        self._urls: Set[str] = set()

    def add_url(self, url: str) -> None:
        u = (url or "").strip().casefold()
        if not u:
            return
        with self._lock:
            self._urls.add(u)

    def has_url(self, url: str) -> bool:
        u = (url or "").strip().casefold()
        if not u:
            return False
        with self._lock:
            return u in self._urls

    def claim_record(self, record: Dict[str, Any]) -> bool:
        """
        Return True if this record's identity is new (claimed).
        False if another host already owns the same person identity.
        """
        keys = identity_keys_for_record(record)
        url = str(record.get("source_url") or "").strip().casefold()
        with self._lock:
            if url and url in self._urls:
                return False
            if keys and any(k in self._keys for k in keys):
                return False
            if url:
                self._urls.add(url)
            for k in keys:
                self._keys.add(k)
            return True

    def seed_from_db(self, db: Any) -> int:
        """Preload identity keys from existing arrests so re-scrapes skip dups."""
        n = 0
        try:
            rows = db._conn.execute(
                "SELECT first_name, middle_name, last_name, full_name, "
                "date_of_birth, age, state, booking_date, arrest_date, "
                "booking_id, source_url, photo_url, photo_path, source_system "
                "FROM arrests"
            ).fetchall()
        except Exception:
            return 0
        with self._lock:
            for row in rows:
                rec = dict(row)
                url = str(rec.get("source_url") or "").strip().casefold()
                if url:
                    self._urls.add(url)
                for k in identity_keys_for_record(rec):
                    self._keys.add(k)
                    n += 1
        return n

    def snapshot_urls(self) -> Set[str]:
        with self._lock:
            return set(self._urls)
