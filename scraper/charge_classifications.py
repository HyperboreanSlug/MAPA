"""
Classify arrest charge text into coarse offense categories for filtering.

Used on import (stored as charge_category) and at query time as fallback.
Primary product still ethnic misclassification; charge filters narrow that analysis.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Sequence, Tuple

# Stable keys used in CLI/GUI filters (order is display order)
CHARGE_CATEGORIES: List[Tuple[str, str]] = [
    ("sex_crimes", "Sex crimes"),
    ("violent", "Violent / assault"),
    ("weapons", "Weapons"),
    ("burglary_be", "Burglary / B&E"),
    ("theft_property", "Theft / property"),
    ("robbery", "Robbery"),
    ("drugs", "Drugs / controlled substances"),
    ("dui_traffic", "DUI / traffic"),
    ("fraud_financial", "Fraud / financial"),
    ("domestic", "Domestic / family"),
    ("public_order", "Public order"),
    ("homicide", "Homicide"),
    ("other", "Other"),
    ("unknown", "Unknown / blank"),
]

CATEGORY_KEYS = [k for k, _ in CHARGE_CATEGORIES]
CATEGORY_LABELS = {k: lab for k, lab in CHARGE_CATEGORIES}


def category_label(key: str) -> str:
    return CATEGORY_LABELS.get((key or "").strip().lower(), key or "Unknown")


def list_category_choices(include_all: bool = True) -> List[str]:
    keys = list(CATEGORY_KEYS)
    if include_all:
        return ["all"] + keys
    return keys


# (category, patterns) — first match wins; order = priority (more specific first)
_RULES: List[Tuple[str, List[str]]] = [
    (
        "homicide",
        [
            r"\bmurder\b", r"\bhomicide\b", r"\bmanslaughter\b",
            r"\bvoluntary\s+manslaughter\b", r"\binvoluntary\s+manslaughter\b",
            r"\bvehicular\s+homicide\b", r"\bcriminal\s+homicide\b",
        ],
    ),
    (
        "sex_crimes",
        [
            r"\brape\b", r"\bsexual\s+assault\b", r"\bsex\s+offense\b",
            r"\bsex\s+offenc", r"\bsexual\s+abuse\b", r"\bsexual\s+battery\b",
            r"\bindecent\s+(libert|expos|assault)", r"\blewd\b",
            r"\bchild\s+mol", r"\bmolest", r"\bsodomy\b",
            r"\bpornograph", r"\bchild\s+porn", r"\bcsam\b",
            r"\bprostitution\b", r"\bsex\s+traffick", r"\bhuman\s+traffick",
            r"\bsolicitation\s+.*(sex|prostitu)", r"\bpandering\b",
            r"\binvasion\s+of\s+privacy.*(sex|intimate)",
            r"\bunlawful\s+sexual", r"\bsexual\s+conduct",
            r"\bforcible\s+fondl", r"\bfondling\b",
            r"\bsex\s+crime", r"\bsexually\s+violent",
            r"\bfailure\s+to\s+register.*(sex|offender)",
            r"\bsex\s+offender", r"\bregistry.*(sex|offender)",
        ],
    ),
    (
        "robbery",
        [
            r"\brobbery\b", r"\barmed\s+robbery\b", r"\bcarjack",
            r"\bstrong.?arm\b",
        ],
    ),
    (
        "burglary_be",
        [
            r"\bburglar", r"\bb\s*&\s*e\b", r"\bb\s+and\s+e\b",
            r"\bbreaking\s+and\s+enter", r"\bbreak\s+and\s+enter",
            r"\bunlawful\s+entry\b", r"\bhome\s+invasion\b",
            r"\benter(ing)?\s+(a\s+)?(dwell|build|struct)",
            r"\bburglary\s+tools\b",
        ],
    ),
    (
        "weapons",
        [
            r"\bfirearm", r"\bhandgun\b", r"\brifle\b", r"\bshotgun\b",
            r"\bweapon", r"\bgun\b", r"\bammunition\b", r"\bconcealed\s+carry",
            r"\bunlawful\s+poss.*weapon", r"\bposs.*firearm",
            r"\bbrandish", r"\bdeadly\s+weapon", r"\bknife\b",
            r"\bexplosive", r"\bdestructive\s+device",
        ],
    ),
    (
        "domestic",
        [
            r"\bdomestic\b", r"\bfamily\s+violence\b", r"\bfamily\s+abuse\b",
            r"\bintimate\s+partner", r"\bprotection\s+order",
            r"\brestraining\s+order", r"\bviolat.*(protect|restrain)",
            r"\bdomestic\s+assault", r"\bdomestic\s+battery",
            r"\bchild\s+abuse\b", r"\bchild\s+endanger", r"\bneglect\s+of\s+child",
            r"\belder\s+abuse\b",
        ],
    ),
    (
        "violent",
        [
            r"\bassault\b", r"\bbattery\b", r"\baggravated\s+assault",
            r"\bfelonious\s+assault", r"\bstalking\b", r"\bharass",
            r"\bkidnap", r"\bfalse\s+imprison", r"\bstrangul",
            r"\bterroristic\s+threat", r"\bthreat\s+to\s+(kill|injure)",
            r"\bmens?\s+rea.*assault", r"\bmayhem\b", r"\briot\b",
            r"\bresist(ing)?\s+(arrest|officer)", r"\baffray\b",
            r"\bintimidation\b", r"\bmalicious\s+wound",
        ],
    ),
    (
        "drugs",
        [
            r"\bcontroll?ed\s+substance", r"\bnarcotic", r"\bdrug\b",
            r"\bcocaine\b", r"\bheroin\b", r"\bfentanyl\b", r"\bmeth(amphetamine)?\b",
            r"\bmarijuana\b", r"\bcannabis\b", r"\bposs(ession)?\s+of\s+.*(drug|marij|cocaine|heroin|meth|fentanyl|opium|opioid)",
            r"\bpossess.*cds\b", r"\bcds\b", r"\bdelivery\s+of\b",
            r"\btraffick.*drug", r"\bdrug\s+traffick", r"\bintent\s+to\s+(distrib|deliver|sell)",
            r"\bparaphernalia\b", r"\bpwid\b",
        ],
    ),
    (
        "dui_traffic",
        [
            r"\bdui\b", r"\bdwi\b", r"\bowi\b", r"\bowi\b",
            r"\bdriving\s+under\s+the\s+influence", r"\bdriving\s+while\s+intoxic",
            r"\bimpaired\s+driving", r"\bbac\b", r"\bblood\s+alcohol",
            r"\breckless\s+driving", r"\bspeeding\b", r"\bhit\s+and\s+run",
            r"\bleave\s+the\s+scene", r"\bno\s+license\b", r"\bsuspended\s+license",
            r"\btraffic\b", r"\bmv\s+offense", r"\bvehicle\s+code",
            r"\buninsured\s+(motor|vehicle)", r"\belude|eluding\b",
        ],
    ),
    (
        "fraud_financial",
        [
            r"\bfraud\b", r"\bforgery\b", r"\bidentity\s+theft", r"\bid\s+theft",
            r"\bembezzl", r"\bcounterfeit", r"\bcredit\s+card", r"\bbad\s+check",
            r"\buttering\b", r"\bwelfare\s+fraud", r"\binsurance\s+fraud",
            r"\bmoney\s+launder", r"\bextortion\b", r"\bbribery\b",
            r"\btheft\s+by\s+deception", r"\bfalse\s+pretense",
        ],
    ),
    (
        "theft_property",
        [
            r"\btheft\b", r"\blarceny\b", r"\bshoplift", r"\bstolen\s+propert",
            r"\breceiv(ing|ed)\s+stolen", r"\bmotor\s+vehicle\s+theft",
            r"\bauto\s+theft", r"\bgrand\s+theft", r"\bpetit\s+theft",
            r"\bpetty\s+theft", r"\bvandal", r"\bcriminal\s+mischief",
            r"\bproperty\s+damage", r"\barson\b", r"\btrespass",
            r"\bunlawful\s+taking",
        ],
    ),
    (
        "public_order",
        [
            r"\bdisorderly\b", r"\bpublic\s+intoxic", r"\bdrunk\s+in\s+public",
            r"\bloitering\b", r"\bcurfew\b", r"\bnoise\b",
            r"\bobstruct(ing)?\s+(justice|officer|police)",
            r"\bfalse\s+report", r"\bperjury\b", r"\bcontempt\b",
            r"\bfugitive\b", r"\bescape\b", r"\bbail\s+jump",
            r"\bwarrant\b", r"\bprobation\s+viol", r"\bparole\s+viol",
            r"\bopen\s+container", r"\blitter",
        ],
    ),
]

_COMPILED: List[Tuple[str, List[re.Pattern]]] = [
    (cat, [re.compile(p, re.IGNORECASE) for p in pats]) for cat, pats in _RULES
]


def _charge_blob(record_or_text: Any) -> str:
    if record_or_text is None:
        return ""
    if isinstance(record_or_text, str):
        return record_or_text
    if not isinstance(record_or_text, dict):
        return str(record_or_text)
    parts = [
        record_or_text.get("charge_description"),
        record_or_text.get("charge_group"),
        record_or_text.get("charge_level"),
        record_or_text.get("charge_class"),
        record_or_text.get("statute"),
        record_or_text.get("offense"),
        record_or_text.get("offense_description"),
    ]
    return " | ".join(str(p) for p in parts if p and str(p).strip())


def classify_charge(record_or_text: Any) -> str:
    """
    Return a category key for charge text or an arrest record dict.

    Empty / unmatchable → "unknown" or "other".
    """
    text = _charge_blob(record_or_text)
    if not text or not text.strip():
        return "unknown"
    for cat, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(text):
                return cat
    return "other"


def classify_record(record: Dict[str, Any]) -> str:
    """Set and return charge_category on *record* (mutates)."""
    cat = classify_charge(record)
    # Prefer pre-set valid category if already classified
    existing = (record.get("charge_category") or "").strip().lower()
    if existing in CATEGORY_LABELS and existing not in ("", "unknown"):
        # re-classify blank/unknown; keep known only if reclass is other? Always reclassify for consistency
        pass
    record["charge_category"] = cat
    return cat


def charge_matches_filter(record: Dict[str, Any], charge_filter: Optional[str]) -> bool:
    """True if record matches charge category filter (None/'all' = always)."""
    if not charge_filter or str(charge_filter).strip().lower() in ("all", "*", ""):
        return True
    want = str(charge_filter).strip().lower()
    have = (record.get("charge_category") or "").strip().lower()
    if not have or have == "unknown":
        have = classify_charge(record)
    return have == want


def summarize_categories(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts: Dict[str, int] = {}
    for r in records:
        cat = (r.get("charge_category") or classify_charge(r)).lower()
        counts[cat] = counts.get(cat, 0) + 1
    out = []
    for key, label in CHARGE_CATEGORIES:
        if key in counts:
            out.append({"category": key, "label": label, "count": counts[key]})
    for key, n in sorted(counts.items(), key=lambda x: -x[1]):
        if key not in CATEGORY_LABELS:
            out.append({"category": key, "label": key, "count": n})
    return out
