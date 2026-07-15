"""Reject non-charges (state names, bare case numbers) and normalize labels.

Used by parsers (on ingest) and by expand/summarize (display of old rows).
"""
from __future__ import annotations

import re
from typing import Iterable, List, Optional, Tuple

from scraper.charge_sanitize_data import CODE_LABELS, NA_VALUES, STATE_NAMES

# Bare docket / case numbers (not offense text). (# must be escaped in VERBOSE.)
_CASE_NUMBER = re.compile(
    r"(?ix)^"
    r"(?:charges?\s+filed\s+)?"
    r"(?:case\s*(?:number|no\.?|\#)\s*:?\s*)?"
    r"(?:"
    r"\d{2,4}\s*[-/]?\s*(?:CR|CF|CM|TR|MC|JD|AJ|CV|SC|DC)\s*[-/]?\s*\d+"
    r"(?:[-/][A-Za-z0-9]+)?"
    r"|"
    r"\d{2,4}[A-Z]{0,4}[-/]CR[-/]?\d+"
    r"|"
    r"[A-Z]{1,4}\d{0,4}[-/]CR[-/]?\d+"
    r")"
    r"\s*$"
)

_SPLIT = re.compile(r"\s*[;|]\s*")
_WORDY = re.compile(r"[A-Za-z]{3,}")
_HTML_TAG = re.compile(r"<[^>]+>")
# Fielded jail dumps: "Description: SPEEDING; Issuing Authority: …; Bond …"
_HAS_FIELDED_DESC = re.compile(
    r"(?i)\bDescription\s*:.*(Issuing\s+Authority|Bond\s+Information|"
    r"Crime\s+Classification|Offense\s+Disposition)"
)
_DESC_FIELD = re.compile(r"(?i)^\s*Description\s*:\s*(.+)$")
_META_FIELD = re.compile(
    r"(?i)^\s*(?:"
    r"Issuing\s+Authority|Offense\s+Disposition|Crime\s+Classification|"
    r"Bond\s+Information|Bond\s+Type|Bond\s+Amount(?:\s+Required)?|"
    r"Disposition|Court(?:\s+Type)?"
    r")\s*:"
)


def _norm(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split()).strip(" \t,.;:-")


def _strip_html(text: str) -> str:
    if not text or "<" not in text:
        return text or ""
    return _norm(_HTML_TAG.sub(" ", text))


def _extract_fielded_descriptions(text: str) -> str:
    """Pull offense lines from Description: fields; drop bond/court chrome."""
    s = _strip_html(text)
    if not s or not _HAS_FIELDED_DESC.search(s):
        return ""
    kept: List[str] = []
    seen = set()
    for part in _SPLIT.split(s) or [s]:
        p = _norm(part)
        if not p or _META_FIELD.match(p):
            continue
        m = _DESC_FIELD.match(p)
        body = _norm(m.group(1)) if m else ""
        if not body:
            continue
        if is_non_charge(body) or _META_FIELD.match(body):
            continue
        key = body.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(body)
    return "; ".join(kept)


def is_case_number(text: str) -> bool:
    """True when *text* is only a docket/case number, not an offense."""
    s = _norm(text)
    if not s:
        return False
    if _CASE_NUMBER.match(s):
        return True
    compact = re.sub(r"\s+", "", s)
    return bool(re.fullmatch(r"(?i)\d{2,4}-?CR-?\d+(?:-[A-Za-z0-9]+)?", compact))


def is_state_name(text: str) -> bool:
    return _norm(text).lower() in STATE_NAMES


def is_non_charge(text: str) -> bool:
    """True when *text* must not be shown as a charge description."""
    from scraper.charge_admin import is_out_of_county_admin

    s = _norm(text)
    if not s:
        return True
    low = s.lower()
    if low in NA_VALUES or low in STATE_NAMES:
        return True
    if is_case_number(s):
        return True
    if "no data to display" in low:
        return True
    if re.search(r"count\s*=\s*0", low) and "offense date" in low:
        return True
    if "offense date" in low and "court type" in low and "bond" in low:
        if not re.search(
            r"[a-z]{4,}",
            re.sub(
                r"(?i)offense date|court type|bond type|charging agency|"
                r"arresting agency|count\s*=\s*\d+|#\d+|charge",
                " ",
                low,
            ),
        ):
            return True
    if is_out_of_county_admin(s):
        return True
    return False


def expand_charge_code(code: str) -> Optional[str]:
    """Map a jail charge code to plain language when possible."""
    raw = _norm(code)
    if not raw:
        return None
    key = raw.upper()
    if key in CODE_LABELS:
        return CODE_LABELS[key]
    if re.fullmatch(r"[\dA-Z]+(?:[.-][\dA-Z]+)+", key) and not _WORDY.search(raw):
        return None
    if " " in raw or len(raw) > 4:
        return raw.title() if raw.isupper() else raw
    return None


def pick_charge(
    code: Optional[str], description: Optional[str]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Choose display charge + optional case_number from code/description pair.

    Returns ``(charge_text, case_number_or_none)``.
    """
    code_s = _norm(code or "")
    desc_s = _norm(description or "")
    case_no: Optional[str] = None

    if desc_s and is_case_number(desc_s):
        case_no = desc_s
        desc_s = ""
    if code_s and is_case_number(code_s):
        case_no = case_no or code_s
        code_s = ""

    if desc_s and not is_non_charge(desc_s):
        return desc_s, case_no

    label = expand_charge_code(code_s) if code_s else None
    if label:
        return label, case_no
    if code_s and not is_non_charge(code_s) and _WORDY.search(code_s):
        shown = code_s if not code_s.isupper() or len(code_s) > 3 else code_s.title()
        return shown, case_no
    return None, case_no


def sanitize_charge_text(text: str) -> str:
    """Drop non-charge segments from a multi-charge string; join survivors."""
    from scraper.charge_chrome import has_charge_table_chrome, strip_charge_table_chrome

    raw = _norm(text)
    if not raw:
        return ""
    raw = _strip_html(raw)
    # Fielded multi-charge dump (Randall County / recentlybooked style)
    fielded = _extract_fielded_descriptions(raw)
    if fielded:
        return fielded
    # Whole-blob chrome extraction first (multi-charge glued without ';')
    if has_charge_table_chrome(raw) and ";" not in raw and "|" not in raw:
        stripped = strip_charge_table_chrome(raw)
        if not stripped or is_non_charge(stripped):
            return ""
        raw = stripped
    parts = [p for p in _SPLIT.split(raw) if p and p.strip()] or [raw]
    kept: List[str] = []
    seen = set()
    for p in parts:
        s = _norm(p)
        if _META_FIELD.match(s):
            continue
        m = _DESC_FIELD.match(s)
        if m:
            s = _norm(m.group(1))
        if has_charge_table_chrome(s) or re.search(r"#\d+", s):
            s = strip_charge_table_chrome(s)
        if not s or is_non_charge(s):
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        kept.append(s)
    return "; ".join(kept)


def first_offense_from_fields(fields: Iterable[Tuple[str, str]]) -> Optional[str]:
    """Pull real offense text from name/value field pairs (e.g. raw_json)."""
    prefer = (
        "offense",
        "offenses",
        "offenses:",
        "crime",
        "crimes",
        "crime information",
        "crime information:",
        "charges",
        "charge",
    )
    by_name = {(_norm(n).lower().rstrip(":")): _norm(v) for n, v in fields if n}
    for key in prefer:
        val = by_name.get(key)
        if val and not is_non_charge(val):
            return sanitize_charge_text(val) or val
    return None
