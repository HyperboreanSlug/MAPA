"""Canonical race keys, display labels, and ethnicity compatibility."""
from __future__ import annotations

import re
from typing import Optional

from .searcher_race_tables import (
    KNOWN_RACE_LABELS,
    _ETHNICITY_COMPATIBLE_RACES,
    _KNOWN_RACE_KEYS,
    _RACE_ALIASES,
)


def _canonical_race_key(recorded_race: str) -> str:
    raw = (recorded_race or "").strip()
    if not raw or raw.upper() in ("N/A", "NA"):
        return "UNKNOWN"
    if raw.isdigit():
        return "UNKNOWN"
    r = " ".join(raw.upper().replace("_", " ").replace("-", " ").split())
    r = r.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
    # Drop punctuation so "American (US)", "Am. Ind" match aliases cleanly.
    r_clean = re.sub(r"[^\w\s/]+", " ", r)
    r_spaced = " ".join(r_clean.replace("/", " ").split())
    if r_spaced in _RACE_ALIASES:
        return _RACE_ALIASES[r_spaced]
    if len(r_spaced) == 1 and r_spaced in _RACE_ALIASES:
        return _RACE_ALIASES[r_spaced]
    if "UNKNOWN" in r_spaced:
        prefix = r_spaced.replace("UNKNOWN", " ").strip()
        if prefix in ("", "U", "UNK", "N/A", "NA"):
            return "UNKNOWN"
    if "NO SELECTION" in r_spaced or r_spaced in ("NOSELECTION", "NOT SELECTED"):
        return "UNKNOWN"
    # Am Ind / Amer Indian abbreviations (not bare "American")
    if (
        r_spaced in ("AM IND", "AMIND")
        or r_spaced.startswith("AM IND ")
        or r_spaced.startswith("AMER INDIAN")
    ):
        return "NATIVE AMERICAN"
    # Bare "American (US)" / "American" (not American Indian) → Other/Unknown
    if r_spaced == "AMERICAN" or r_spaced.startswith("AMERICAN US"):
        return "OTHER"
    if r_spaced in ("OTHER ASIAN", "ASIAN OTHER", "OTHER ASIAN PACIFIC ISLANDER"):
        return "OTHER ASIAN"
    if "OTHER" in r_spaced and "ASIAN" in r_spaced:
        return "OTHER ASIAN"
    if "HISPANIC" in r_spaced and "WHITE" in r_spaced:
        return "WHITE HISPANIC"
    if "HISPANIC" in r_spaced or "LATINO" in r_spaced or "LATINA" in r_spaced:
        return "HISPANIC"
    if (
        "AMERICAN INDIAN" in r_spaced
        or "NATIVE AMERICAN" in r_spaced
        or "ALASKA NATIVE" in r_spaced
    ):
        return "NATIVE AMERICAN"
    # MENA (Middle East / North Africa) shares stated-race bucket with Indian
    if (
        "MIDDLE EASTERN" in r_spaced
        or "NORTH AFRICAN" in r_spaced
        or "NORTH AFRICA" in r_spaced
        or r_spaced in ("MENA", "NEMA", "INDIAN MENA", "INDIAN NEMA")
        or ("INDIAN" in r_spaced and ("MENA" in r_spaced or "NEMA" in r_spaced))
    ):
        return "INDIAN"
    words = r_spaced.split()
    if "BLACK" in words or "AFRICAN AMERICAN" in r_spaced:
        return "BLACK"
    # Afr Amer / Afro-American abbreviations
    if "AFR" in words and any(w.startswith("AMER") for w in words):
        return "BLACK"
    if r_spaced.startswith("WHITE") or r_spaced.endswith(" WHITE"):
        return "WHITE"
    if (
        "OTHER" in words
        or r_spaced in ("OT", "MULTI RACIAL", "MULTIRACIAL")
        or ("MULTI" in words and "RACIAL" in words)
    ):
        return "OTHER"
    # Asian + Pacific Islander (incl. abbreviated "Pac. Isl.") → one bucket
    if "ASIAN" in r_spaced and (
        "PACIFIC" in r_spaced
        or "PAC ISL" in r_spaced
        or "PAC ISLAND" in r_spaced
        or re.search(r"\bPAC\b", r_spaced)
    ):
        return "ASIAN"
    if r_spaced in (
        "PACIFIC ISLANDER",
        "NATIVE HAWAIIAN",
        "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER",
    ) or "PACIFIC ISLAND" in r_spaced:
        return "ASIAN"
    # Bare ASIAN word after other Asian checks
    if "ASIAN" in words:
        return "ASIAN"
    # Never surface charge/gender/docket garbage as a race key
    if r_spaced in _KNOWN_RACE_KEYS:
        return r_spaced
    return "UNKNOWN"


def format_race_label(recorded_race: str) -> str:
    raw = (recorded_race or "").strip()
    # Accept already-merged display labels (dropdown selection → filter)
    lowered = raw.lower().replace("  ", " ")
    if lowered in ("indian / mena", "indian/mena", "indian / nema", "indian/nema"):
        return "Indian / MENA"
    if lowered in ("other/unknown", "other / unknown"):
        return "Other/Unknown"
    if lowered in (
        "asian",
        "asian or pac isl",
        "asian or pacific islander",
        "asian / pacific islander",
        "asian/pacific islander",
        "pacific islander",
    ):
        return "Asian"
    if lowered in ("native american", "american indian"):
        return "Native American"
    key = _canonical_race_key(recorded_race)
    if key in ("UNKNOWN", "OTHER"):
        return "Other/Unknown"
    if key == "WHITE HISPANIC":
        return "White"
    if key == "INDIAN":
        # Shared bucket: South Asian Indian + MENA stated-race values
        return "Indian / MENA"
    if key in ("ASIAN", "ASIAN / PACIFIC ISLANDER", "PACIFIC ISLANDER", "OTHER ASIAN"):
        return "Asian"
    if key == "NATIVE AMERICAN":
        return "Native American"
    if key == "WHITE":
        return "White"
    if key == "BLACK":
        return "Black"
    if key == "HISPANIC":
        return "Hispanic"
    # Unknown canonical keys must not become charge-like title-cased labels
    if key not in _KNOWN_RACE_KEYS:
        return "Other/Unknown"
    if len(key) <= 2:
        return "Other/Unknown"
    label = key.title().replace("Or", "or").replace("/ ", "/")
    if label not in KNOWN_RACE_LABELS:
        return "Other/Unknown"
    return label

def _ethnicity_family(likely_ethnicity: str) -> str:
    eth = (likely_ethnicity or "").strip().lower()
    if eth == "indian" or eth.startswith("indian") or "high_confidence" in eth:
        return "indian"
    if eth.startswith("asian"):
        return "asian"
    if eth.startswith("european"):
        return "european"
    if eth.startswith("african (") or eth == "african":
        return "african"
    if eth in ("african american", "african-american"):
        return "african_american"
    if eth in ("native american", "native-american"):
        return "native_american"
    if eth == "hispanic":
        return "hispanic"
    if eth == "jewish":
        return "jewish"
    if eth == "portuguese":
        return "portuguese"
    if eth == "arabic":
        return "arabic"
    return eth.replace(" ", "_")


def _is_other_or_other_asian(race_key: str) -> bool:
    r = (race_key or "").strip().upper()
    if r in ("OTHER", "OTHER ASIAN", "UNKNOWN"):
        return True
    if "OTHER" in r and "ASIAN" in r:
        return True
    return False


def _has_hispanic_ethnicity(recorded_ethnicity: Optional[str]) -> bool:
    eth = (recorded_ethnicity or "").strip().upper()
    if not eth:
        return False
    if re.search(r"\bNON[\s\-]?HISPANIC\b", eth) or "NOT HISPANIC" in eth:
        return False
    markers = (
        "HISPANIC", "LATINO", "LATINA", "LATINX",
        "HISPANIC OR LATINO", "LATINO OR HISPANIC",
    )
    if any(m in eth for m in markers):
        return True
    if eth in ("H", "HIS", "HISP"):
        return True
    return False


def _is_compatible(
    likely_ethnicity: str,
    recorded_race: str,
    recorded_ethnicity: Optional[str] = None,
) -> bool:
    if not recorded_race or not likely_ethnicity or likely_ethnicity == "Unknown":
        return True
    family = _ethnicity_family(likely_ethnicity)
    race = _canonical_race_key(recorded_race)
    if family == "indian" and _is_other_or_other_asian(race):
        return True
    if family == "hispanic" and race in ("UNKNOWN", "OTHER"):
        return True
    if family == "hispanic" and race == "WHITE":
        return _has_hispanic_ethnicity(recorded_ethnicity)
    if race == "BLACK" and family in ("european", "jewish", "portuguese"):
        return True
    compatible = _ETHNICITY_COMPATIBLE_RACES.get(family)
    if not compatible:
        return race == likely_ethnicity.strip().upper()
    if race in compatible:
        return True
    raw_u = " ".join((recorded_race or "").strip().upper().split())
    return raw_u in compatible
