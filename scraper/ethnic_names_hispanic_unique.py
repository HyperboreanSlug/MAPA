"""Shared White/Hispanic surname rules for misclassification detection.

Surnames that appear on both Hispanic and European lists need a Hispanic
given-name signal for high Hispanic confidence. ``Martin`` was removed from
``hispanic_surnames`` permanently (Anglo/French surname noise); keep this
hook for any future shared-list surnames.
"""
from __future__ import annotations

from typing import Optional

# Primarily Anglo/European surnames that also appear on Hispanic lists.
# High Hispanic confidence requires a Hispanic first/middle name signal.
# Martin is no longer on hispanic_surnames (removed permanently).
_SHARED_HISPANIC_WHITE_SURNAMES = frozenset()


def is_shared_hispanic_white_surname(surname: Optional[str]) -> bool:
    """True when the surname is common to White and Hispanic populations."""
    s = (surname or "").strip().lower()
    if not s:
        return False
    return s in _SHARED_HISPANIC_WHITE_SURNAMES
