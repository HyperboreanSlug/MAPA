"""Database constants, insert column maps, and helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

DEFAULT_DB_PATH = "data/arrests.db"
SCHEMA_VERSION = 4

_MERGE_SEP = " | "

_MERGE_UNION_FIELDS = frozenset({
    "state", "county", "city", "agency", "jurisdiction",
    "charge_description", "charge_group", "charge_level", "charge_class",
    "charge_category", "statute", "case_number", "booking_id",
    "source_url", "source_id", "source_system",
    "arrest_date", "booking_date", "address",
    "photo_url", "photo_path", "html_path",
    "hair", "eyes", "height", "weight",
})

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
    "photo_url", "photo_path", "html_path",
    "hair", "eyes", "height", "weight",
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
