"""Browse Misclassify column labels, verification, and actual-race buckets."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from scraper.searcher import ethnicity_review_verdict

BROWSE_COLS = [
    "name",
    "race",
    "actual",
    "review",
    "charge",
    "state",
    "date",
    "source",
]
BROWSE_LABELS = {
    "name": "Name",
    "race": "Stated race",
    "actual": "Actual race",
    "review": "Verification",
    "charge": "Charge",
    "state": "State",
    "date": "Date",
    "source": "Source",
}
# Verification status filter (default Unverified).
VERIFICATION_FILTERS = [
    "Unverified",
    "Confirmed correct",
    "Confirmed incorrect",
    "All",
]
VERIFICATION_QUERY = {
    "unverified": "unreviewed",
    "unreviewed": "unreviewed",
    "confirmed correct": "correct",
    "correct": "correct",
    "confirmed incorrect": "incorrect",
    "incorrect": "incorrect",
    "all": None,
}

# Browse actual-race picker / filter: four coarse buckets only.
BROWSE_ACTUAL_RACES = ["White", "Black", "Hispanic", "MENA"]

# Stored / analyzer labels → bucket (lowercase keys).
_ACTUAL_RACE_TO_BUCKET = {
    "white": "White",
    "european": "White",
    "portuguese": "White",
    "jewish": "White",
    "black": "Black",
    "african american": "Black",
    "african-american": "Black",
    "hispanic": "Hispanic",
    "latino": "Hispanic",
    "latina": "Hispanic",
    "latinx": "Hispanic",
    "arabic": "MENA",
    "arab": "MENA",
    "mena": "MENA",
    "indian / mena": "MENA",
    "indian/mena": "MENA",
    "middle eastern": "MENA",
    "middle-eastern": "MENA",
    "north african": "MENA",
    "north-african": "MENA",
}


def verification_query(label: Optional[str]) -> Optional[str]:
    key = (label or "Unverified").strip().lower()
    if key in VERIFICATION_QUERY:
        return VERIFICATION_QUERY[key]
    return "unreviewed"


def verification_label(record: Dict[str, Any]) -> str:
    verdict = ethnicity_review_verdict(record)
    if verdict == "correct":
        return "Confirmed correct"
    if verdict == "incorrect":
        return "Confirmed incorrect"
    return "Unverified"


def bucket_actual_race(label: Optional[str]) -> Optional[str]:
    """Map a free-form actual/likely label to White/Black/Hispanic/MENA."""
    raw = " ".join(str(label or "").replace("_", " ").split()).strip()
    if not raw:
        return None
    hit = _ACTUAL_RACE_TO_BUCKET.get(raw.lower())
    if hit:
        return hit
    # Prefix match: "European (english)" → White
    low = raw.lower()
    for key, bucket in _ACTUAL_RACE_TO_BUCKET.items():
        if low.startswith(key) or key in low.split():
            return bucket
    return None


def actual_race_filter_values(bucket: str) -> List[str]:
    """DB values that count as *bucket* (includes the bucket name itself)."""
    b = (bucket or "").strip()
    if not b:
        return []
    out = {b}
    if b.lower() == "white":
        out.update({"White", "European", "Portuguese", "Jewish"})
    elif b.lower() == "black":
        out.update({"Black", "African American", "African-American"})
    elif b.lower() == "hispanic":
        out.update({"Hispanic", "Latino", "Latina"})
    elif b.lower() == "mena":
        out.update({"MENA", "Arabic", "Arab", "Middle Eastern"})
    return sorted(out)


def picker_actual_race(label: Optional[str], options: List[str]) -> str:
    """Value to show in a bucketed actual-race combo.

    Never inject charge/docket junk into the dropdown: if the label cannot be
    mapped to a known option, fall back to the first option (or Unknown).
    """
    raw = " ".join(str(label or "").split()).strip() or "Unknown"
    opts = list(options or [])
    if opts and set(opts) <= set(BROWSE_ACTUAL_RACES):
        bucket = bucket_actual_race(raw)
        if bucket and bucket in opts:
            return bucket
        if raw in opts:
            return raw
        return opts[0] if opts else "Unknown"
    if raw in opts:
        return raw
    bucket = bucket_actual_race(raw)
    if bucket and bucket in opts:
        return bucket
    # Prefer Unknown when present rather than prepending garbage
    for fallback in ("Unknown", "Other", "White"):
        if fallback in opts:
            return fallback
    return opts[0] if opts else "Unknown"


def actual_from_stated_race(recorded_race: Optional[str]) -> Optional[str]:
    """
    Map stated race → Browse actual-race value when marked classified correctly.

    Prefers White / Black / Hispanic / MENA; otherwise returns a clean display
    label (e.g. Asian) when the stated race is known.
    """
    from scraper.searcher import format_race_label

    raw = str(recorded_race or "").strip()
    if not raw:
        return None
    label = format_race_label(raw)
    low = label.lower()
    if "mena" in low or low == "indian":
        return "MENA"
    bucket = bucket_actual_race(label) or bucket_actual_race(raw)
    if bucket:
        return bucket
    if label and label not in ("Other/Unknown", "—", ""):
        return label
    return None
