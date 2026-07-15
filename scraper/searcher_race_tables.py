"""Race alias tables for canonical race key normalization."""
from __future__ import annotations

_ETHNICITY_COMPATIBLE_RACES = {
    "hispanic": {
        "HISPANIC", "LATINO", "LATINA", "LATINX", "H",
        "WHITE HISPANIC", "HISPANIC OR LATINO", "LATINO OR HISPANIC",
    },
    "asian": {
        "ASIAN", "ASIAN / PACIFIC ISLANDER", "ASIAN/PACIFIC ISLANDER",
        "PACIFIC ISLANDER", "A", "API", "CHINESE", "KOREAN", "JAPANESE",
        "VIETNAMESE", "FILIPINO", "OTHER ASIAN",
    },
    "indian": {
        "ASIAN", "ASIAN / PACIFIC ISLANDER", "ASIAN/PACIFIC ISLANDER",
        "ASIAN INDIAN", "EAST INDIAN", "INDIAN", "SOUTH ASIAN",
        "A", "API", "OTHER", "OTHER ASIAN", "UNKNOWN", "U",
    },
    "african_american": {
        "BLACK", "AFRICAN AMERICAN", "AFRICAN-AMERICAN", "B",
        "BLACK OR AFRICAN AMERICAN",
    },
    "native_american": {
        "NATIVE AMERICAN", "AMERICAN INDIAN",
        "AMERICAN INDIAN OR ALASKA NATIVE", "ALASKA NATIVE", "I", "N", "NATIVE",
    },
    "arabic": {"WHITE", "OTHER", "MIDDLE EASTERN", "ARAB", "W"},
    # Anglo / European surnames are common among Black Americans (not a
    # race misclassification). Do not flag race=Black as "should be White".
    "jewish": {"WHITE", "OTHER", "BLACK", "W", "B"},
    "portuguese": {"WHITE", "HISPANIC", "OTHER", "BLACK", "W", "B"},
    "european": {"WHITE", "CAUCASIAN", "BLACK", "W", "B"},
    "african": {
        "BLACK", "AFRICAN AMERICAN", "AFRICAN-AMERICAN", "B",
        "BLACK OR AFRICAN AMERICAN",
    },
}

_RACE_ALIASES = {
    "W": "WHITE", "CAUCASIAN": "WHITE", "CAUCASION": "WHITE", "WHITE": "WHITE",
    "WHITE OR CAUCASIAN": "WHITE", "CAUCASIAN OR WHITE": "WHITE",
    "B": "BLACK", "BLACK": "BLACK", "AFRICAN AMERICAN": "BLACK",
    "AFRICAN-AMERICAN": "BLACK", "BLACK OR AFRICAN AMERICAN": "BLACK",
    "BLACK/AFRICAN AMERICAN": "BLACK", "BLACK AFRICAN AMERICAN": "BLACK",
    "H": "HISPANIC", "L": "HISPANIC", "LATINO": "HISPANIC", "LATINA": "HISPANIC",
    "LATINX": "HISPANIC", "HISPANIC": "HISPANIC",
    "HISPANIC OR LATINO": "HISPANIC", "LATINO OR HISPANIC": "HISPANIC",
    "HISPANIC/LATINO": "HISPANIC", "LATINO/HISPANIC": "HISPANIC",
    "A": "ASIAN", "API": "ASIAN", "ASIAN": "ASIAN",
    # Asian + Pacific Islander booking labels share one stated-race bucket
    "ASIAN OR PAC ISL": "ASIAN",
    "ASIAN OR PAC ISLANDER": "ASIAN",
    "ASIAN OR PACIFIC ISLANDER": "ASIAN",
    "ASIAN OR PACIFIC ISL": "ASIAN",
    "ASIAN PACIFIC ISLANDER": "ASIAN",
    "ASIAN / PACIFIC ISLANDER": "ASIAN",
    "ASIAN/PACIFIC ISLANDER": "ASIAN",
    "PACIFIC ISLANDER": "ASIAN",
    "NATIVE HAWAIIAN": "ASIAN",
    "NATIVE HAWAIIAN OR OTHER PACIFIC ISLANDER": "ASIAN",
    "P": "ASIAN",
    "U": "UNKNOWN", "UNK": "UNKNOWN", "UNKNOWN": "UNKNOWN",
    "N/A": "UNKNOWN", "NA": "UNKNOWN", "NONE": "UNKNOWN", "NULL": "UNKNOWN",
    "": "UNKNOWN",
    # LAPD descent codes often used in open data
    "C": "WHITE",
    "F": "ASIAN",
    "K": "ASIAN",
    "J": "ASIAN",
    "V": "ASIAN",
    "Z": "ASIAN",
    "I": "NATIVE AMERICAN",
    # Single-letter "N" is used as Native American in some booking feeds
    # (distinct from N/A / NA which map to UNKNOWN above).
    "N": "NATIVE AMERICAN",
    "AMERICAN INDIAN": "NATIVE AMERICAN",
    "AMERICAN INDIAN OR ALASKA": "NATIVE AMERICAN",
    "AMERICAN INDIAN OR ALASKA NATIVE": "NATIVE AMERICAN",
    "AMER INDIAN/ALASKA NATIVE": "NATIVE AMERICAN",
    "NATIVE AMERICAN": "NATIVE AMERICAN",
    "ALASKA NATIVE": "NATIVE AMERICAN",
    # Common booking abbreviation for American Indian / Alaska Native
    "AM IND": "NATIVE AMERICAN",
    "AM. IND": "NATIVE AMERICAN",
    "AMIND": "NATIVE AMERICAN",
    "O": "OTHER",
    "OTHER": "OTHER",
    # Bare "American" (not American Indian) → Other/Unknown for stated-race filters.
    "AMERICAN": "OTHER",
    "AMERICAN (US)": "OTHER",
    "AMERICAN US": "OTHER",
    # Explicit non-answers → Other/Unknown (with UNKNOWN / N/A)
    "NO SELECTION": "UNKNOWN",
    "NOSELECTION": "UNKNOWN",
    "X": "UNKNOWN",
    "G": "OTHER",
    # South Asian Indian + MENA (Middle East / North Africa) share one stated-race bucket
    "INDIAN": "INDIAN",
    "ASIAN INDIAN": "INDIAN",
    "EAST INDIAN": "INDIAN",
    "SOUTH ASIAN": "INDIAN",
    "MENA": "INDIAN",
    "NEMA": "INDIAN",
    "MIDDLE EASTERN": "INDIAN",
    "MIDDLE EASTERN OR NORTH A": "INDIAN",
    "MIDDLE EASTERN OR NORTH AFRICAN": "INDIAN",
    "MIDDLE EASTERN OR NORTH AFRICA": "INDIAN",
    "NORTH AFRICAN": "INDIAN",
    # Common booking / OCR variants
    "AFR AMER": "BLACK",
    "AFR AMERICAN": "BLACK",
    "AFRO AMERICAN": "BLACK",
    "MEXICAN": "HISPANIC",
    "MEXICANO": "HISPANIC",
    "UNKOWN": "UNKNOWN",  # common misspelling
    "NATIVE": "NATIVE AMERICAN",
}

# Canonical keys that may leave _canonical_race_key (anything else → UNKNOWN).
_KNOWN_RACE_KEYS = frozenset({
    "WHITE",
    "BLACK",
    "HISPANIC",
    "ASIAN",
    "NATIVE AMERICAN",
    "INDIAN",
    "OTHER",
    "UNKNOWN",
    "WHITE HISPANIC",
    "OTHER ASIAN",
    "ASIAN / PACIFIC ISLANDER",
    "PACIFIC ISLANDER",
})

# Display labels used by Browse / filter dropdowns (never charge fragments).
KNOWN_RACE_LABELS = frozenset({
    "White",
    "Black",
    "Hispanic",
    "Asian",
    "Native American",
    "Indian / MENA",
    "Other/Unknown",
})
