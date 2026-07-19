"""Shared helpers for RecentlyBooked HTML parsers."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from bs4 import Tag

BASE_URL = "https://recentlybooked.com"
# Booking id after "_" may be empty (e.g. /ca/sacramento/name~1210_).
_DETAIL_PATH = re.compile(
    r"^/([a-z]{2})/([a-z0-9-]+)/([^/]+~([a-z0-9-]+)_([a-z0-9-]*))/?$",
    re.IGNORECASE,
)
_LABEL_ALIASES = {
    "race": "race",
    "sex": "sex",
    "gender": "sex",
    "age": "age",
    "booking date": "booking_date",
    "booked date": "booking_date",
    "booking date/time": "booking_date",
    "arrest date": "arrest_date",
    "charge": "charge_description",
    "charges": "charge_description",
    "charge description": "charge_description",
    "agency": "agency",
    "arresting agency": "agency",
    "facility": "facility",
    "booking id": "booking_id",
    "height": "height",
    "weight": "weight",
    "hair": "hair",
    "eyes": "eyes",
}
_NAME_SUFFIXES = {
    "jr",
    "jr.",
    "sr",
    "sr.",
    "ii",
    "iii",
    "iv",
    "v",
    "2nd",
    "3rd",
    "4th",
}


def _text(tag: Optional[Tag]) -> Optional[str]:
    if tag is None:
        return None
    value = tag.get_text(" ", strip=True)
    return value or None


# "July 6, 2026 8:50 PM" and similar card/detail stamps
_HUMAN_DT_FMTS = (
    "%B %d, %Y %I:%M %p",
    "%B %d, %Y %H:%M",
    "%B %d, %Y",
    "%b %d, %Y %I:%M %p",
    "%b %d, %Y %H:%M",
    "%b %d, %Y",
    "%m/%d/%Y %I:%M %p",
    "%m/%d/%Y",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
)


def normalize_booking_datetime(raw: Any) -> Dict[str, str]:
    """Parse human RB dates into ISO ``booking_date`` / ``arrest_date``.

    Browse orders by ``arrest_date``; RB historically stored only
    ``July 6, 2026 8:50 PM`` in ``booking_date`` with empty ``arrest_date``,
    so website rows never appeared in the top Browse page.
    """
    s = re.sub(r"\s+", " ", str(raw or "").strip())
    if not s:
        return {}
    # Already ISO date (optional time / T)
    m_iso = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T\s].*)?$", s)
    if m_iso:
        day = m_iso.group(1)
        out = {"booking_date": day, "arrest_date": day}
        tm = re.search(r"(?:T|\s)(\d{1,2}:\d{2})", s)
        if tm:
            out["arrest_time"] = tm.group(1)[:5]
        return out
    for fmt in _HUMAN_DT_FMTS:
        try:
            dt = datetime.strptime(s, fmt)
        except ValueError:
            continue
        day = dt.strftime("%Y-%m-%d")
        out = {"booking_date": day, "arrest_date": day}
        if "%H" in fmt or "%I" in fmt:
            out["arrest_time"] = dt.strftime("%H:%M")
        return out
    return {"booking_date": s}


def apply_booking_dates(record: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize booking/arrest fields on a record dict in place."""
    raw = record.get("booking_date") or record.get("arrest_date") or ""
    parsed = normalize_booking_datetime(raw)
    if not parsed:
        return record
    if parsed.get("booking_date"):
        record["booking_date"] = parsed["booking_date"]
    if parsed.get("arrest_date") and not str(record.get("arrest_date") or "").strip():
        record["arrest_date"] = parsed["arrest_date"]
    elif parsed.get("arrest_date") and not re.match(
        r"^\d{4}-\d{2}-\d{2}", str(record.get("arrest_date") or "")
    ):
        record["arrest_date"] = parsed["arrest_date"]
    if parsed.get("arrest_time") and not record.get("arrest_time"):
        record["arrest_time"] = parsed["arrest_time"]
    return record


def _detail_match(url: str) -> Optional[re.Match[str]]:
    return _DETAIL_PATH.match(urlparse(url).path)


def _name_parts(name: Optional[str]) -> Dict[str, str]:
    if not name:
        return {}
    cleaned = " ".join(name.replace(",", " ").split())
    parts = cleaned.split()
    if not parts:
        return {}
    result: Dict[str, str] = {"full_name": cleaned, "name": cleaned}
    suffix_parts: List[str] = []
    while len(parts) > 1 and parts[-1].lower() in _NAME_SUFFIXES:
        suffix_parts.insert(0, parts.pop())
    if suffix_parts:
        result["name_suffix"] = " ".join(suffix_parts)
    if len(parts) == 1:
        result["last_name"] = parts[0]
    else:
        result["first_name"] = parts[0]
        result["last_name"] = parts[-1]
        if len(parts) > 2:
            result["middle_name"] = " ".join(parts[1:-1])
    return result
