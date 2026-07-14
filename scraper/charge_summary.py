"""Summarize raw charge text into short stable labels for misclassify tables.

Expands jail abbreviations first, then maps to standardized labels.
Example: "A ASSLT CBI FV" → "DOMESTIC VIOLENCE"
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Sequence

from scraper.charge_expand import expand_charge_text
from scraper.charge_summary_rules import _COMPILED

# Split multi-charge blobs from jails that concatenate bookings.
# Do not split letter+/ tokens (e.g. W/DEADLY WEAPON).
_SPLIT = re.compile(r"\s*[;|]\s*|\s{2,}|(?<![A-Za-z])\s*/\s*(?=[A-Z])")
_NOISE = re.compile(
    r"(?i)"
    r"(\$\d[\d,.]*)|"
    r"(active\s+bond\b.*$)|"
    r"(bond-\d+\w*)|"
    r"(n/a)+"
)
# Jail case class / docket tails and MTR booking prefixes.
_STRIP_PREFIX = re.compile(r"(?i)^\s*MTR\s*[-–—:]\s*")
_STRIP_OOC = re.compile(r"(?i)^\s*out\s+of\s+county(?:\s+hold)?\s*[/:\-]\s*")


def _clean_segment(text: str) -> str:
    s = " ".join((text or "").replace("\u00a0", " ").split())
    s = _NOISE.sub(" ", s)
    s = _STRIP_PREFIX.sub("", s)
    # OUT OF COUNTY/POS MARIJ… → keep offense body when present
    m = _STRIP_OOC.match(s)
    if m:
        body = s[m.end() :].strip()
        from scraper.charge_admin import is_place_case_blob
        from scraper.charge_sanitize import is_non_charge

        if body and not is_place_case_blob(body) and not is_non_charge(body):
            body = re.split(
                r"\s*/\s*(?=[A-Z][A-Z\s]+(?:CO|COUNTY)\b)", body, maxsplit=1
            )[0]
            s = body
    s = re.sub(r"\s+", " ", s).strip(" \t,.;:-")
    return s


def _split_charges(blob: str) -> List[str]:
    raw = _clean_segment(blob)
    if not raw:
        return []
    parts = [p for p in _SPLIT.split(raw) if p and p.strip()]
    out: List[str] = []
    seen_l: set = set()
    for p in parts:
        c = _clean_segment(p)
        key = c.lower()
        if not c or key in seen_l:
            continue
        if len(c) < 2:
            continue
        seen_l.add(key)
        out.append(c)
    return out or ([raw] if raw else [])


def _match_one(segment: str) -> str:
    # Expand abbreviations so rules see full language.
    text = expand_charge_text(segment).strip() or segment.strip()
    if not text:
        return ""
    for label, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return label
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) > 48:
        compact = compact[:45].rstrip() + "…"
    return compact


def summarize_charge(record_or_text: Any) -> str:
    """
    Return a short standardized label for charge text or an arrest record.

    Multi-charge strings are expanded, split, summarized, then unique labels
    joined with ``; `` (priority order preserved).
    """
    from scraper.charge_expand import expand_charge
    from scraper.charge_sanitize import is_non_charge, sanitize_charge_text

    if record_or_text is None:
        return "—"
    if isinstance(record_or_text, dict):
        # Prefer full expand (includes raw_json offense recovery).
        blob = expand_charge(record_or_text)
        if blob in ("", "—"):
            return "—"
    else:
        blob = sanitize_charge_text(str(record_or_text))
        if not blob or is_non_charge(blob):
            return "—"
    segments = _split_charges(blob)
    if not segments:
        return "—"
    labels: List[str] = []
    seen: set = set()
    for seg in segments:
        if is_non_charge(seg):
            continue
        lab = _match_one(seg)
        if not lab or is_non_charge(lab):
            continue
        key = lab.upper()
        if key in seen:
            continue
        seen.add(key)
        labels.append(lab)
    return "; ".join(labels) if labels else "—"


def summarize_charge_list(records: Sequence[Dict[str, Any]]) -> List[str]:
    return [summarize_charge(r) for r in records]
