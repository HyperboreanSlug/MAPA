"""Compiled charge rules. Combines split rule tables."""
from __future__ import annotations

import re
from typing import List, Tuple

from scraper.charge_rules_a import _RULES_A
from scraper.charge_rules_b import _RULES_B

_RULES: List[Tuple[str, List[str]]] = [*_RULES_A, *_RULES_B]

_COMPILED: List[Tuple[str, List[re.Pattern]]] = [
    (cat, [re.compile(p, re.IGNORECASE) for p in pats]) for cat, pats in _RULES
]
