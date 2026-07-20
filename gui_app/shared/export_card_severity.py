"""Severity ranking for export-card charge ordering (sex crimes first)."""
from __future__ import annotations

import re
from typing import List

# Higher = listed first on export cards.
_TIERS: list[tuple[int, re.Pattern[str]]] = [
    (
        100,
        re.compile(
            r"(?i)\b(?:"
            r"rape|sexual\s+assault|sexual\s+battery|sex\s+assault|"
            r"lewd|lascivious|molest|indecent(?:cy)?\s+with|"
            r"child\s+porn|child\s+sex|sex(?:ual)?\s+abuse|"
            r"sodomy|incest|voyeur|fondl|idsi|"
            r"criminal\s+sexual|gross\s+sexual|"
            r"corruption\s+of\s+(?:a\s+)?minors?|"
            r"sex\s+traffick|continuous\s+sexual"
            r")\b"
        ),
    ),
    (90, re.compile(r"(?i)\b(?:murder|homicide|manslaughter)\b")),
    (85, re.compile(r"(?i)\b(?:kidnap|abduct|false\s+imprison|unlawful\s+restraint)\b")),
    (80, re.compile(r"(?i)\b(?:child\s+abuse|child\s+endanger|endanger.*minor)\b")),
    (
        70,
        re.compile(
            r"(?i)\b(?:aggravated\s+assault|assault\s+with|deadly\s+weapon|"
            r"firearm|weapon|shooting)\b"
        ),
    ),
    (65, re.compile(r"(?i)\b(?:domestic|family\s+violence|battering)\b")),
    (60, re.compile(r"(?i)\b(?:robbery|carjack)\b")),
    (55, re.compile(r"(?i)\b(?:burglar|break(?:ing)?\s+(?:and\s+)?enter)\b")),
    (50, re.compile(r"(?i)\b(?:assault|battery|strangul)\b")),
    (
        40,
        re.compile(
            r"(?i)\b(?:controlled\s+substance|cocaine|heroin|fentanyl|"
            r"meth|drug|marijuana|cannabis)\b"
        ),
    ),
    (35, re.compile(r"(?i)\b(?:dui|dwi|owi|intoxicat|under\s+the\s+influence)\b")),
    (
        25,
        re.compile(
            r"(?i)\b(?:giving\s+underage|alcohol|under\s+21|underage|"
            r"furnish.*alcohol|serving\s+alcohol)\b"
        ),
    ),
    (15, re.compile(r"(?i)\b(?:theft|larceny|stolen|shoplift)\b")),
    (10, re.compile(r"(?i)\b(?:failure\s+to\s+appear|warrant|probation|parole|hold|ice)\b")),
]


def charge_severity(label: str) -> int:
    """Numeric severity for one charge phrase (higher = more severe)."""
    t = (label or "").strip()
    if not t:
        return 0
    best = 5
    for score, pat in _TIERS:
        if pat.search(t):
            best = max(best, score)
    # Slight boost when a sex charge names a child / young victim age.
    if best >= 100 and re.search(
        r"(?i)\b(?:child|minor|under\s+\d|victim\s+\d|1[0-5])\b", t
    ):
        best += 5
    if best >= 100 and re.search(
        r"(?i)\b(?:molest|battery|rape|assault|penetrat)\b", t
    ):
        best += 3
    return best


def sort_charges_by_severity(parts: List[str]) -> List[str]:
    """Stable sort: highest severity first; ties keep input order."""
    indexed = list(enumerate(parts))
    indexed.sort(key=lambda iv: (-charge_severity(iv[1]), iv[0]))
    return [p for _, p in indexed]
