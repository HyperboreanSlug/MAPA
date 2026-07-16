"""Stable record keys + content hashes for public DB delta sync."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, Tuple

# Columns exported into delta upserts (no autoincrement id).
# Must match arrests schema (see scraper.database.constants._ARREST_COLUMNS).
SYNC_ROW_COLUMNS: Tuple[str, ...] = (
    "first_name",
    "middle_name",
    "last_name",
    "full_name",
    "race",
    "ethnicity",
    "sex",
    "gender",
    "age",
    "date_of_birth",
    "arrest_date",
    "arrest_time",
    "booking_date",
    "release_date",
    "agency",
    "jurisdiction",
    "state",
    "county",
    "city",
    "address",
    "latitude",
    "longitude",
    "charge_description",
    "charge_group",
    "charge_level",
    "charge_class",
    "charge_category",
    "statute",
    "case_number",
    "booking_id",
    "source_id",
    "source_url",
    "source_system",
    "raw_json",
    "likely_ethnicity",
    "name_confidence",
    "flags",
    "photo_url",
    "photo_path",
    "html_path",
    "hair",
    "eyes",
    "height",
    "weight",
)

_HASH_FIELDS = SYNC_ROW_COLUMNS


def _norm(s: Any) -> str:
    return " ".join(str(s or "").strip().casefold().split())


def sync_record_key(record: Dict[str, Any]) -> str:
    """
    Stable public key for one arrest row.

    Prefer ``source_url`` (primary unique identity for scrapes). Fall back to a
    soft identity hash so rows without a URL still participate in deltas.
    """
    rec = record or {}
    url = _norm(rec.get("source_url"))
    if url:
        return "u:" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:24]

    soft = "|".join(
        (
            _norm(rec.get("source_system")),
            _norm(rec.get("source_id")),
            _norm(rec.get("first_name")),
            _norm(rec.get("last_name")),
            _norm(rec.get("date_of_birth")),
            _norm(rec.get("state")),
            _norm(rec.get("county")),
            _norm(rec.get("booking_id")),
            _norm(rec.get("booking_date") or rec.get("arrest_date")),
            _norm(rec.get("photo_url")),
            _norm(rec.get("full_name")),
        )
    )
    if soft.replace("|", ""):
        return "s:" + hashlib.sha1(soft.encode("utf-8")).hexdigest()[:24]
    blob = json.dumps(
        {k: rec.get(k) for k in ("full_name", "charge_description", "raw_json")},
        sort_keys=True,
        default=str,
        ensure_ascii=False,
    )
    return "x:" + hashlib.sha1(blob.encode("utf-8")).hexdigest()[:24]


def row_content_hash(record: Dict[str, Any]) -> str:
    """SHA-1 of canonical field payload (change detector for deltas)."""
    payload = []
    for col in _HASH_FIELDS:
        v = record.get(col)
        if v is None:
            payload.append((col, None))
        elif isinstance(v, float):
            payload.append((col, round(v, 6)))
        else:
            payload.append((col, v))
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def row_to_sync_dict(record: Dict[str, Any]) -> Dict[str, Any]:
    """Export only known columns for delta transport."""
    out: Dict[str, Any] = {}
    for col in SYNC_ROW_COLUMNS:
        if col in record:
            out[col] = record.get(col)
    return out


def dict_from_sqlite_row(row: Any, columns: Iterable[str]) -> Dict[str, Any]:
    cols = list(columns)
    if hasattr(row, "keys"):
        return {c: row[c] for c in cols if c in row.keys()}
    return {c: row[i] for i, c in enumerate(cols)}
