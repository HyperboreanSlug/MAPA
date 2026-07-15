"""Normalize arrest/booking field names to a canonical schema."""

from __future__ import annotations

from typing import Any, Dict, Optional


CANONICAL_FIELDS = (
    "first_name", "middle_name", "last_name", "full_name",
    "race", "ethnicity", "sex", "gender", "age", "date_of_birth",
    "arrest_date", "arrest_time", "booking_date", "release_date",
    "agency", "jurisdiction", "state", "county", "city", "address",
    "latitude", "longitude",
    "charge_description", "charge_group", "charge_level", "charge_class",
    "statute", "case_number", "booking_id",
    "source_id", "source_url", "source_system", "raw_json",
    "hair", "eyes", "height", "weight",
)


def clean_key(key: Any) -> str:
    if key is None:
        return ""
    return str(key).replace("\ufeff", "").strip()


def clean_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def apply_field_map(row: Dict[str, Any], field_map: Dict[str, str]) -> Dict[str, Any]:
    """Copy row and apply explicit source→canonical renames."""
    out: Dict[str, Any] = {}
    # First pass: all keys lower-normalized
    for k, v in row.items():
        ck = clean_key(k)
        if not ck:
            continue
        out[ck] = clean_value(v)

    # Explicit map (source column as published)
    for src, dest in (field_map or {}).items():
        # try exact and case-insensitive
        val = None
        if src in row:
            val = clean_value(row[src])
        else:
            for k, v in row.items():
                if clean_key(k).lower() == src.lower():
                    val = clean_value(v)
                    break
        if val is not None:
            out[dest] = val

    # Generic Title Case → snake
    for k in list(out.keys()):
        if " " in k or k[:1].isupper():
            snake = k.lower().replace(" ", "_").replace("-", "_")
            out.setdefault(snake, out[k])

    # Gender alias
    if not out.get("sex") and out.get("gender"):
        out["sex"] = out["gender"]
    if not out.get("gender") and out.get("sex"):
        out["gender"] = out["sex"]

    # Build full_name
    if not out.get("full_name"):
        parts = [
            p for p in (out.get("first_name"), out.get("middle_name"), out.get("last_name"))
            if p
        ]
        if parts:
            out["full_name"] = " ".join(str(p) for p in parts)
    if not out.get("last_name") and out.get("full_name"):
        parts = str(out["full_name"]).replace(",", " ").split()
        if len(parts) >= 2:
            out.setdefault("first_name", parts[0])
            out.setdefault("last_name", parts[-1])
        elif parts:
            out.setdefault("last_name", parts[0])

    return out


def stamp_source(
    record: Dict[str, Any],
    *,
    source_id: str,
    state: str,
    jurisdiction: str,
) -> Dict[str, Any]:
    record = dict(record)
    record.setdefault("source_system", source_id)
    record.setdefault("state", state)
    record.setdefault("jurisdiction", jurisdiction)
    if record.get("source_id") and not record.get("source_url"):
        record["source_url"] = f"{source_id}:{record['source_id']}"
    elif not record.get("source_url"):
        # synthetic unique-ish key for dedupe when only name+date
        key = "|".join(
            str(record.get(k) or "")
            for k in ("last_name", "first_name", "arrest_date", "booking_date", "charge_description")
        )
        if key.strip("|"):
            record["source_url"] = f"{source_id}:{key}"
    return record
