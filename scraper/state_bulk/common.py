"""Shared helpers for named state DOC bulk imports."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

BATCH = 2000


def log(msg: str) -> None:
    print(msg, flush=True)


def clean(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, float) and value != value:  # NaN
        return None
    text = str(value).strip()
    return text if text else None


def parse_last_first(name: Optional[str]) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Parse 'LAST, FIRST M.' → (first, middle, last)."""
    raw = clean(name)
    if not raw:
        return None, None, None
    raw = re.sub(r"\s+", " ", raw)
    if "," in raw:
        last, rest = raw.split(",", 1)
        parts = rest.strip().split()
        first = parts[0] if parts else None
        middle = " ".join(parts[1:]) if len(parts) > 1 else None
        return _title(first), _title(middle), _title(last)
    parts = raw.split()
    if len(parts) >= 2:
        return _title(parts[0]), _title(" ".join(parts[1:-1]) or None), _title(parts[-1])
    return None, None, _title(parts[0] if parts else None)


def _title(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    # ponytail: strip digits/ID tokens leaked from fixed-width parsing
    parts = []
    for p in value.split():
        cleaned = re.sub(r"\d+", "", p)
        if cleaned:
            parts.append(cleaned.capitalize())
    return " ".join(parts) if parts else None


def normalize_sex(value: Optional[str]) -> Optional[str]:
    v = clean(value)
    if not v:
        return None
    u = v.upper()
    if u in ("M", "MALE"):
        return "Male"
    if u in ("F", "FEMALE"):
        return "Female"
    return v.title()


def normalize_race(value: Optional[str]) -> Optional[str]:
    v = clean(value)
    if not v:
        return None
    u = v.upper().replace(".", "")
    mapping = {
        "W": "White",
        "WHITE": "White",
        "B": "Black",
        "BLACK": "Black",
        "H": "Hispanic",
        "HISPANIC": "Hispanic",
        "A": "Asian",
        "ASIAN": "Asian",
        "I": "American Indian",
        "AMERICAN INDIAN": "American Indian",
        "AI": "American Indian",
        "O": "Other",
        "OTHER": "Other",
        "U": None,
        "UNKNOWN": None,
    }
    if u in mapping:
        return mapping[u]
    # Verbose labels (VT DOC, census-style)
    if "AFRICAN" in u or u.startswith("BLACK"):
        return "Black"
    if "WHITE" in u and "HISPANIC" not in u:
        return "White"
    if "HISPANIC" in u or "LATINO" in u:
        return "Hispanic"
    if "ASIAN" in u or "PACIFIC" in u:
        return "Asian"
    if "NATIVE" in u or "INDIAN" in u or "ALASKA" in u:
        return "American Indian"
    return v.title()


def excel_serial_to_iso(value: Any) -> Optional[str]:
    """Convert Excel date serial or date-like value to YYYY-MM-DD."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, (int, float)):
        # Guard absurd / sentinel serials
        try:
            n = float(value)
        except (TypeError, ValueError):
            return None
        if n < 1000 or n > 80000:
            return None
        try:
            # Excel 1900 date system
            base = datetime(1899, 12, 30)
            dt = base + timedelta(days=n)
            if dt.year < 1900 or dt.year > 2100:
                return None
            return dt.date().isoformat()
        except (OverflowError, ValueError):
            return None
    text = clean(value)
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%Y/%m/%d"):
        try:
            return datetime.strptime(text[:10], fmt).date().isoformat()
        except ValueError:
            continue
    return text[:10] if re.match(r"\d{4}-\d{2}-\d{2}", text) else None


def flush_batch(db: Any, batch: List[Dict[str, Any]], totals: Dict[str, int], *, force: bool) -> None:
    if not batch:
        return
    r = db.import_records(batch, skip_existing_urls=not force)
    totals["imported"] += r.get("imported", 0)
    totals["skipped"] += r.get("skipped", 0)
    totals["skipped_identity"] += r.get("skipped_identity", 0)
    batch.clear()


def raw_json(payload: Dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, default=str, separators=(",", ":"))
