"""Shared White/Hispanic surname rules for misclassification detection.

Some surnames appear on both Hispanic and European lists (notably Martin —
English/French Martin vs Spanish Martín). Name analysis alone must not mark
race=White as Hispanic for those without a Hispanic given-name signal.
"""
from __future__ import annotations

from typing import Optional

# Primarily Anglo/European surnames that also appear on Hispanic lists.
# High Hispanic confidence requires a Hispanic first/middle name signal.
_SHARED_HISPANIC_WHITE_SURNAMES = frozenset({
    "martin",  # English/French Martin; Spanish Martín is the same token
})


def is_shared_hispanic_white_surname(surname: Optional[str]) -> bool:
    """True when the surname is common to White and Hispanic populations."""
    s = (surname or "").strip().lower()
    if not s:
        return False
    return s in _SHARED_HISPANIC_WHITE_SURNAMES
