"""Name extractors and ethnicity-review flag helpers."""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


def ethnicity_review_verdict(record: Optional[Dict[str, Any]]) -> str:
    """Return ``correct`` / ``incorrect`` / ```` from arrests.flags JSON."""
    if not record:
        return ""
    flags = record.get("flags")
    if isinstance(flags, str) and flags.strip():
        try:
            flags = json.loads(flags)
        except (TypeError, json.JSONDecodeError, ValueError):
            return ""
    if not isinstance(flags, dict):
        return ""
    return str(flags.get("ethnicity_review") or "").strip().lower()


_SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "v", "esq", "jr.", "sr.", "2nd", "3rd", "4th"}

def _strip_suffix(parts: list) -> list:
    out = list(parts)
    while out and out[-1].lower().strip(".-") in _SUFFIXES:
        out.pop()
    return out


def _last_name_from_record(record: Dict[str, Any]) -> str:
    last = (record.get("last_name") or record.get("LastName") or "").strip()
    if last:
        toks = _strip_suffix(last.replace(",", " ").split())
        return toks[-1] if toks else ""
    full = (record.get("full_name") or record.get("Name") or "").strip()
    if full:
        parts = _strip_suffix(full.replace(",", " ").split())
        if parts:
            return parts[-1]
    return ""


def _first_name_from_record(record: Dict[str, Any]) -> str:
    first = (record.get("first_name") or record.get("FirstName") or "").strip()
    if first:
        return first.split()[0]
    full = (record.get("full_name") or record.get("Name") or "").strip()
    if full:
        parts = full.replace(",", " ").split()
        if len(parts) >= 2:
            return parts[0]
    return ""


def _middle_name_from_record(record: Dict[str, Any]) -> str:
    mid = (record.get("middle_name") or record.get("MiddleName") or "").strip()
    if mid:
        return mid
    first = (record.get("first_name") or record.get("FirstName") or "").strip()
    if first:
        parts = first.split()
        if len(parts) >= 2:
            return " ".join(parts[1:])
    full = (record.get("full_name") or record.get("Name") or "").strip()
    if full:
        parts = full.replace(",", " ").split()
        if len(parts) >= 3:
            return " ".join(parts[1:-1])
    return ""
