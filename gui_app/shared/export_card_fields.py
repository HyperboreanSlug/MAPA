"""Field extractors and fonts for export mugshot cards."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional

from PIL import ImageFont

_WATERMARK = "@DoDeportations"
_SEAL_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "department_of_deportations_seal.png"
)
_CARD_W = 1080
_CARD_H = 1350
# Default mug height (previous card look). Shrinks only when crime needs room.
_PHOTO_H = 820
_PHOTO_H_MIN = 560
_PHOTO_TOP = 48
_BG = (12, 12, 14, 255)
_PANEL = (26, 26, 32, 255)
_TEXT = (236, 236, 241, 255)
_MUTED = (155, 155, 168, 255)
_ACCENT = (232, 168, 124, 255)
_BANNER_RED = (180, 28, 36, 255)
_BANNER_TEXT = (255, 255, 255, 255)


def os_environ_get(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def desktop_dir() -> Path:
    home = Path.home()
    for name in ("Desktop", "OneDrive/Desktop", "OneDrive/Рабочий стол"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    desktop = home / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]+", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned) or "arrest"
    return cleaned[:80]


def load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    windir = Path(os_environ_get("WINDIR", r"C:\Windows"))
    candidates = []
    if bold:
        candidates.extend(
            [
                windir / "Fonts" / "segoeuib.ttf",
                windir / "Fonts" / "arialbd.ttf",
                windir / "Fonts" / "calibrib.ttf",
            ]
        )
    candidates.extend(
        [
            windir / "Fonts" / "segoeui.ttf",
            windir / "Fonts" / "arial.ttf",
            windir / "Fonts" / "calibri.ttf",
        ]
    )
    for path in candidates:
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def person_name(record: Mapping[str, Any]) -> str:
    full = str(record.get("full_name") or "").strip()
    if full:
        return full
    parts = [
        str(record.get("first_name") or "").strip(),
        str(record.get("middle_name") or "").strip(),
        str(record.get("last_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p) or "Unknown"


def location(record: Mapping[str, Any]) -> str:
    county = str(record.get("county") or "").strip()
    state = str(record.get("state") or "").strip().upper()
    city = str(record.get("city") or "").strip()
    bits = []
    if city:
        bits.append(city.title())
    if county:
        c = county.replace("-", " ").replace("_", " ").title()
        if not c.lower().endswith("county"):
            c = f"{c} County"
        bits.append(c)
    if state:
        bits.append(state)
    return ", ".join(bits) or "Unknown location"


def crime(record: Mapping[str, Any], *, max_labels: int = 5) -> str:
    """Descriptive charge line for export cards (plain language when possible).

    Prefers expanded offense text (including recovery from raw_json) over coarse
    table buckets like \"SEX OFFENSE\", so cards state the actual crime.
    """
    from scraper.charge_expand import expand_charge
    from scraper.charge_summary import summarize_charge

    full = expand_charge(record)
    if full and full != "—":
        polished = _polish_card_charge(full)
        if polished:
            return _card_charge_text(_limit_charge_labels(polished, max_labels))
    summary = summarize_charge(record)
    if summary and summary not in ("—", "OTHER"):
        return _card_charge_text(_limit_charge_labels(summary, max_labels))
    cat = str(record.get("charge_category") or "").strip()
    return cat.replace("_", " ").title() if cat else "Unknown charge"


def _limit_charge_labels(text: str, max_labels: int) -> str:
    """Keep the first N semicolon-separated labels so cards stay readable."""
    if max_labels <= 0:
        return text
    parts = [p.strip() for p in str(text or "").split(";") if p.strip()]
    if len(parts) <= max_labels:
        return "; ".join(parts)
    return "; ".join(parts[:max_labels]) + "; …"


_CARD_ACRONYMS = {
    "Dui": "DUI",
    "Dwi": "DWI",
    "Owi": "OWI",
    "Ovi": "OVI",
    "Fta": "FTA",
    "Ice": "ICE",
    "Id": "ID",
    "Dl": "DL",
    "Mv": "MV",
    "Be": "B&E",
    "Usc": "USC",
}

# Leading statute / booking codes before the offense words.
_LEADING_CODE = re.compile(
    r"(?ix)^\s*"
    r"(?:"
    r"(?:\d+\s*[.\-]\s*)+\d+\s*[-–—:]\s+"  # 97.5.23 -  / 5 - 14 - 108 -
    r"|\d{2,5}\s*[-–—:]\s+"  # 0950 -
    r"|\d+\s+Usc\b[\w\s().]*?[-–—]\s+"  # 18 USC 2252A(a)(2) -
    r")"
)
_ATTEMPT = re.compile(
    r"(?i)\bAttempt(?:ed)?\s+To\s+Commit\b|\bAttempt(?:ed)?\s+To\b|\bAttempt\b(?=\s+\w)"
)
_ORDINAL_DEGREE = re.compile(
    r"\b(\d+)\s*[-–—]?\s*(?:St|Nd|Rd|Th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
# Jail shorthand glued to digits: 3RD / 2ND / 1ST (optionally + OR MORE)
_ORDINAL_GLUED = re.compile(
    r"\b(\d+)(st|nd|rd|th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
_PAGE_JUNK = re.compile(r"(?i)\s*[-–—]?\s*Page\s*:\s*\d+.*$")
_PAREN_META = re.compile(
    r"\([^)]*(?:Lev|Deg|Count|Principal|Page)[^)]*\)",
    re.IGNORECASE,
)
_TRAILING_ROLE = re.compile(
    r"(?i)\s*[-–—]\s*(?:Principal|Accomplice|Aider|Abettor)\b.*$"
)
_BAC_FRAG = re.compile(r"(?i)\s*[.\-]\s*0?\.\d{1,3}\b|\s+\.\s+\d{2}\b")
_SEX_CHILD = re.compile(
    r"(?i)\b((?:Aggravated\s+)?(?:Sexual\s+)?(?:Assault|Abuse|Battery|Rape))"
    r"\s+Child\b"
)
_SMALL_WORDS = frozenset(
    {"A", "An", "And", "Of", "Or", "The", "To", "For", "In", "On", "By", "With"}
)


def _ordinal_degree(match: re.Match) -> str:
    n = int(match.group(1))
    mod100 = n % 100
    if 10 < mod100 < 14:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf} Degree"


def _polish_card_charge(text: str) -> str:
    """Strip codes/meta and normalize phrasing for share-card readability."""
    parts: list[str] = []
    for raw in str(text or "").split(";"):
        s = " ".join(raw.split()).strip(" -–—:")
        if not s:
            continue
        s = _PAGE_JUNK.sub("", s)
        s = _PAREN_META.sub(" ", s)
        s = _TRAILING_ROLE.sub("", s)
        s = _LEADING_CODE.sub("", s)
        s = _ATTEMPT.sub("Attempted", s)
        s = _ORDINAL_GLUED.sub(_ordinal_degree, s)
        s = _ORDINAL_DEGREE.sub(_ordinal_degree, s)
        s = _SEX_CHILD.sub(r"\1 of a Child", s)

        s = _BAC_FRAG.sub("", s)
        s = re.sub(r"\s+", " ", s).strip(" -–—:;")
        if s:
            parts.append(s)
    return "; ".join(parts)


def _title_token(word: str) -> str:
    """Title-case a token; DRIVER'S → Driver's (not Driver'S)."""
    if not word:
        return word
    letters = re.sub(r"[^A-Za-z]", "", word)
    if letters and letters.isupper() and any(c in word for c in "'’"):
        return word[0].upper() + word[1:].lower()
    if word.isupper() and word.isalpha() and len(word) > 1:
        return word.title()
    return word


def _card_charge_text(text: str) -> str:
    """Title-case charge lines for readable card layout; fix small words/acronyms."""
    parts: list[str] = []
    for raw in str(text or "").split(";"):
        s = " ".join(raw.split()).strip()
        if not s:
            continue
        s = re.sub(r"\(\s+", "(", s)
        s = re.sub(r"\s+\)", ")", s)
        if s.isupper() and any(c.isalpha() for c in s):
            s = s.title()
        words = s.split()
        fixed: list[str] = []
        for i, w in enumerate(words):
            # Strip trailing punctuation for acronym lookup
            core, punct = w, ""
            if w and w[-1] in ".,;:":
                core, punct = w[:-1], w[-1]
            if i > 0 and core in _SMALL_WORDS:
                fixed.append(core.lower() + punct)
            elif core in _CARD_ACRONYMS:
                fixed.append(_CARD_ACRONYMS[core] + punct)
            else:
                titled = _title_token(core)
                key = titled[:1].upper() + titled[1:] if titled else titled
                fixed.append(_CARD_ACRONYMS.get(key, titled) + punct)
        s = " ".join(fixed)
        s = re.sub(
            r"\b(" + "|".join(_CARD_ACRONYMS.keys()) + r")\b",
            lambda m: _CARD_ACRONYMS.get(m.group(1), m.group(1)),
            s,
        )
        parts.append(s)
    return "; ".join(parts) if parts else str(text or "").strip()


def arrest_datetime(record: Mapping[str, Any]) -> str:
    date = str(record.get("arrest_date") or record.get("booking_date") or "").strip()
    time = str(record.get("arrest_time") or "").strip()
    if not date:
        return "Unknown"
    if "T" in date:
        d, _, t = date.partition("T")
        date = d
        if not time and t:
            time = t[:5]
    if time:
        return f"{date} {time}".strip()
    return date
