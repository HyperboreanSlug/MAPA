"""Detect admin transfer / place-docket blobs that are not real charges."""
from __future__ import annotations

import re

_OFFENSE_HINT = re.compile(
    r"(?i)\b("
    r"poss|theft|assault|asslt|burglar|robbery|rape|sexual|marij|cannabis|"
    r"drug|weapon|firearm|murder|homicide|dui|dwi|evad|elud|flee|fraud|"
    r"forgery|battery|kidnap|traffick|meth|cocaine|heroin|felony|misd"
    r")\b"
)
_OOC_PREFIX = re.compile(r"(?i)^out\s+of\s+county(?:\s+hold)?\b")


def _norm(text: str) -> str:
    return " ".join((text or "").replace("\u00a0", " ").split()).strip(" \t,.;:-")


def is_place_case_blob(text: str) -> bool:
    """True when text is only place / docket / class (F|M), not an offense."""
    s = _norm(text)
    if not s:
        return True
    if _OFFENSE_HINT.search(s):
        return False
    t = re.sub(r"\d+", " ", s)
    t = re.sub(
        r"(?i)\b(co|county|st|state|warrant|hold|for|other|agency|jim)\b",
        " ",
        t,
    )
    t = re.sub(r"(?i)\b[fm]\b", " ", t)
    t = re.sub(r"[^a-zA-Z]+", " ", t)
    return len(t.split()) <= 3


def is_out_of_county_admin(text: str) -> bool:
    """True for OUT OF COUNTY transfer lines with no real offense."""
    s = _norm(text)
    if not s or not _OOC_PREFIX.match(s):
        return False
    body = re.sub(r"(?i)^out\s+of\s+county(?:\s+hold)?\s*[/:\-]?\s*", "", s)
    if is_place_case_blob(body):
        return True
    if re.search(r"(?i)\b(hold|warrant)\b", s) and not _OFFENSE_HINT.search(s):
        return True
    return False
