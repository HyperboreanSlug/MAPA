"""Polish charge text for export cards. Uses split tables."""
from __future__ import annotations

import re

from gui_app.shared.export_card_polish_data import *  # noqa: F401,F403
from gui_app.shared.export_card_polish_data import _CARD_ACRONYMS
from gui_app.shared.export_card_severity import sort_charges_by_severity

def limit_charge_labels(text: str, max_labels: int) -> str:
    """Keep the first N charge labels so cards stay readable."""
    if max_labels <= 0:
        return text
    raw = str(text or "")
    if " · " in raw:
        parts = [p.strip() for p in raw.split(" · ") if p.strip()]
        sep = " · "
    else:
        parts = [p.strip() for p in raw.split(";") if p.strip()]
        sep = " · "
    if len(parts) <= max_labels:
        return sep.join(parts)
    return sep.join(parts[:max_labels]) + " · …"


def _ordinal_degree(match: re.Match) -> str:
    n = int(match.group(1))
    mod100 = n % 100
    if 10 < mod100 < 14:
        suf = "th"
    else:
        suf = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf} Degree"


def _rewrite_card_phrases(s: str) -> str:
    """Map long boilerplate offense strings to short card labels."""
    if _ALCOHOL_UNDERAGE.search(s):
        s = _ALCOHOL_UNDERAGE.sub("Giving Underage Alcohol", s)
    # 12YOA / 12 yoa / years of age → yo
    s = _YOA_GLUED.sub(r"\1 yo", s)
    s = _YOA_WORD.sub("yo", s)
    s = _YEARS_OF_AGE.sub("yo", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Any ICE/immigration-hold phrasing → one canonical card label (no duplicates).
_ICE_PART = re.compile(
    r"(?i)\bice\b|\bi\.?\s*c\.?\s*e\.?\b|\bimmig\w*|\bdetainer\b"
    r"|\bins\s+hold\b|\bdhs\s+hold\b"
)
_ICE_LABEL = "Immigration and Customs Hold"

_DROP_UNLESS_ONLY = re.compile(
    r"(?i)arrest\s+on\s+failure\s+to\s+obey\s+written\s+promise\s+to\s+appear"
    r"|\bVOP\b"
    r"|\bviolation\s+of\s+probation\b"
    r"|\bprobation\s+viol"
    r"|\bparole\s+viol"
    r"|\binterfere?\w*\s+w(?:ith)?\s*emergency\s+req"
    r"|\bpublic\s+order\s+crimes?\b"
    r"|\b2\s+way\s+comm(?:unication)?\s+device\b"
)
_VOP_REDUNDANT = re.compile(r"(?i)\bVOP\s*\(VOP\)\s*VOP\b")
_STATUTE_NUM = re.compile(
    r"\s*\b\d{1,3}[.\-]\d{1,4}(?:\([A-Za-z0-9]+\)){0,2}(?=\s|$|[;,.])"
)
_BARE_STATUTE = re.compile(r"(?:^|[;·]\s*)\d{6,10}\s*(?=$|[;·])")
_JAIL_COLON = re.compile(r"\s*:\s+")


def polish_card_charge(text: str) -> str:
    """Strip codes/meta and normalize phrasing for share-card readability."""
    parts: list[str] = []
    seen: set[str] = set()
    for raw in str(text or "").split(";"):
        s = " ".join(raw.split()).strip(" -–—:")
        if not s:
            continue
        s = _PAGE_JUNK.sub("", s)
        s = _CARD_TRAIL_META.sub("", s)
        s = _PAREN_META.sub(" ", s)
        s = _PAREN_JAIL_CODE.sub(" ", s)
        s = _BARE_JAIL_CODE.sub(" ", s)
        s = _DEFENDANT_OVER.sub(" ", s)
        s = _OFFENDER_AGE.sub(" ", s)
        s = _TRAILING_ROLE.sub("", s)
        s = _LEADING_CODE.sub("", s)
        s = _OVERCOME_WILL.sub(" ", s)
        s = _WITH_SLASH.sub("With ", s)
        s = _DOT_ORDINAL.sub(" ", s)
        s = _CLASS_TAIL.sub("", s)
        s = _ATTEMPT.sub("Attempted", s)
        s = _ORDINAL_GLUED.sub(_ordinal_degree, s)
        s = _ORDINAL_DEGREE.sub(_ordinal_degree, s)
        s = _DEGREE_DEG.sub(r"\1", s)
        s = _BARE_DEG.sub(r"\1 Degree", s)
        s = _SEX_CHILD.sub(r"\1 of a Child", s)
        s = _BAC_FRAG.sub("", s)
        s = _VOP_REDUNDANT.sub("VOP", s)
        s = _STATUTE_NUM.sub("", s)
        s = _JAIL_COLON.sub(" ", s)
        s = _rewrite_card_phrases(s)
        s = re.sub(r"\s+", " ", s).strip(" -–—:;")
        s = re.sub(r"\(\s*\)", "", s)
        s = re.sub(r"\s+", " ", s).strip(" -–—:;.")
        if _ICE_PART.search(s):
            s = _ICE_LABEL
        if not s or re.fullmatch(r"\d{4,10}", s):
            continue
        key = s.casefold()
        if key in seen:
            continue
        seen.add(key)
        parts.append(s)
    if len(parts) > 1:
        parts = [p for p in parts if not _DROP_UNLESS_ONLY.search(p)]
    parts = sort_charges_by_severity(parts)
    return "; ".join(parts)


def _proper_word(core: str, *, first: bool) -> str:
    """Force proper case for one word; known acronyms stay uppercase."""
    if not core:
        return core
    low = core.lower()
    if low in _CARD_ACRONYMS:
        return _CARD_ACRONYMS[low]
    om = re.fullmatch(r"(\d+)(st|nd|rd|th)", low)
    if om:
        return om.group(1) + om.group(2)
    if re.fullmatch(r"[\d$.,<>%=+\-]+", core):
        return core
    if not first and low in _SMALL_WORDS:
        return low
    if "-" in core and not core.startswith("-"):
        bits = core.split("-")
        return "-".join(
            _proper_word(b, first=(first and i == 0)) for i, b in enumerate(bits)
        )
    if re.search(r"[A-Za-z]", core):
        return low[:1].upper() + low[1:] if low else core
    return core


def normalize_charge_separators(text: str) -> str:
    """Structural joins → middle-dot `` · `` only (parity with SORPA)."""
    t = text or ""
    # Protect victim age ranges (12 - 15) before hyphen→middot conversion.
    ages: list[str] = []

    def _keep_age(m: re.Match) -> str:
        ages.append(f"{m.group(1)}-{m.group(2)}")
        return f"{_AGE_RANGE_TOKEN}{len(ages) - 1}{_AGE_RANGE_TOKEN}"

    t = _AGE_RANGE.sub(_keep_age, t)
    t = re.sub(r"\s*[—–]\s*", " · ", t)
    t = re.sub(r"\s+-\s+", " · ", t)
    t = re.sub(r"\s*;\s*", " · ", t)
    t = re.sub(r"(?:\s*·\s*)+", " · ", t)
    t = re.sub(r"\s{2,}", " ", t)
    for i, val in enumerate(ages):
        t = t.replace(f"{_AGE_RANGE_TOKEN}{i}{_AGE_RANGE_TOKEN}", val)
    return t.strip(" ·;,|")


def card_charge_text(text: str) -> str:
    """Proper-case every charge line (no mixed ALLCAPS/Title leftovers)."""
    text = normalize_charge_separators(text)
    parts: list[str] = []
    for raw in str(text or "").split(" · "):
        s = " ".join(raw.split()).strip()
        if not s:
            continue
        s = re.sub(r"\(\s+", "(", s)
        s = re.sub(r"\s+\)", ")", s)
        words = s.split()
        fixed: list[str] = []
        for i, w in enumerate(words):
            m = _AFFIX.match(w)
            pre, core, suf = m.groups() if m else ("", w, "")
            fixed.append(pre + _proper_word(core, first=(i == 0)) + suf)
        parts.append(" ".join(fixed))
    return " · ".join(parts) if parts else str(text or "").strip()
