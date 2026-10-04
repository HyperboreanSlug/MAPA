"""Card polish tables. Regex and constants only."""
from __future__ import annotations

import re

__all__ = ["_AFFIX", "_AGE_RANGE", "_AGE_RANGE_TOKEN", "_ALCOHOL_UNDERAGE", "_ATTEMPT", "_BAC_FRAG", "_BARE_DEG", "_BARE_JAIL_CODE", "_CARD_ACRONYMS", "_CARD_TRAIL_META", "_CLASS_TAIL", "_DEFENDANT_OVER", "_DEGREE_DEG", "_DOT_ORDINAL", "_LEADING_CODE", "_OFFENDER_AGE", "_ORDINAL_DEGREE", "_ORDINAL_GLUED", "_OVERCOME_WILL", "_PAGE_JUNK", "_PAREN_JAIL_CODE", "_PAREN_META", "_SEX_CHILD", "_SMALL_WORDS", "_TRAILING_ROLE", "_WITH_SLASH", "_YEARS_OF_AGE", "_YOA_GLUED", "_YOA_WORD"]


# Kept as full uppercase on cards (never mixed case).
_CARD_ACRONYMS = {
    "dui": "DUI",
    "dwi": "DWI",
    "owi": "OWI",
    "ovi": "OVI",
    "fta": "FTA",
    "ice": "ICE",
    "id": "ID",
    "dl": "DL",
    "mv": "MV",
    "be": "B&E",
    "b&e": "B&E",
    "usc": "USC",
    "leo": "LEO",
    "dv": "DV",
    "vop": "VOP",
    "pv": "PV",
}

# Leading statute / booking codes before the offense words.
_LEADING_CODE = re.compile(
    r"(?ix)^\s*"
    r"(?:"
    r"(?:\d+\s*[.\-]\s*)+\d+\s*[-–—:]\s+"  # 97.5.23 -  / 5 - 14 - 108 -
    r"|\d{2,5}\s*[-–—:]\s+"  # 0950 -
    r"|\d+\s+Usc\b[\w\s().]*?[-–—]\s+"  # 18 USC 2252A(a)(2) -
    r")"
)
_ATTEMPT = re.compile(
    r"(?i)\bAttempt(?:ed)?\s+To\s+Commit\b|\bAttempt(?:ed)?\s+To\b|\bAttempt\b(?=\s+\w)"
)
_ORDINAL_DEGREE = re.compile(
    r"\b(\d+)\s*[-–—]?\s*(?:St|Nd|Rd|Th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
_ORDINAL_GLUED = re.compile(
    r"\b(\d+)(st|nd|rd|th)\b(?:\s+Degree)?",
    re.IGNORECASE,
)
_PAGE_JUNK = re.compile(r"(?i)\s*[-–—]?\s*Page\s*:\s*\d+.*$")
_PAREN_META = re.compile(
    r"\([^)]*(?:Lev|Deg|Count|Principal|Page)[^)]*\)",
    re.IGNORECASE,
)
# Jail statute crumbs: (MISC0325) (LEWD1456) (LEWD 1454) (LEDS1456)
_PAREN_JAIL_CODE = re.compile(
    r"\((?:"
    r"[A-Z]{2,12}\s*\d{2,6}"
    r"|LE[DW]S?\s*\d{3,6}"
    r")\)",
    re.IGNORECASE,
)
# Bare trailing codes when not already parenthetical.
_BARE_JAIL_CODE = re.compile(
    r"(?i)\s*\b(?:LEWD|LEDS|LEWS|MISC|FS|ORS|RCW|PC|HS)\s*\d{3,6}\b"
)
# Element language: age-of-defendant / principal status, not a crime.
_DEFENDANT_OVER = re.compile(
    r"(?i)\s*(?:[\-(]\s*)?defendant\s+(?:is\s+)?(?:over|age)\s*18"
    r"(?:\s+years?(?:\s+of\s+age)?)?(?:\s+or\s+older)?\s*[\-)]?"
    r"|\s*\(\s*defendant\s+over\s*18\s*\)"
)
# Offender-age element (same idea as defendant-over-18), not a separate crime.
_OFFENDER_AGE = re.compile(
    r"(?i)\s+offender\s*(?:[><=]+\s*)?\d+\s*(?:yoa?|years?(?:\s+of\s+age)?)?"
    r"(?:\s+or\s+older)?\b"
    r"|\s+offender\s+\d+\s*(?:yoa?|years?(?:\s+of\s+age)?)?\s+or\s+older\b"
)
_TRAILING_ROLE = re.compile(
    r"(?i)\s*[-–—]\s*(?:Principal|Accomplice|Aider|Abettor)\b.*$"
)
_BAC_FRAG = re.compile(r"(?i)\s*[.\-]\s*0?\.\d{1,3}\b|\s+\.\s+\d{2}\b")
_SEX_CHILD = re.compile(
    r"(?i)\b((?:Aggravated\s+)?(?:Sexual\s+)?(?:Assault|Abuse|Battery|Rape))"
    r"\s+Child\b"
)
_OVERCOME_WILL = re.compile(r"(?i)\s+overcome\s+victim'?s?\s+will\b")
_CARD_TRAIL_META = re.compile(
    r"(?is)\s+(?:"
    r"Conviction\s+Date|"
    r"Date\s+Convicted|"
    r"Year\s+of\s+Last(?:\s+Conviction|\s+Release)?|"
    r"Conviction\s+State|"
    r"Release\s+Date|"
    r"Date\s+Released|"
    r"Sentence\s+Date|"
    r"Sentence\s+Length|"
    r"Offense\s+Code\b|"
    r"Jurisdiction\b|"
    r"Place\s+of\s+Crime|"
    r"Victim\s+of\s+Crime"
    r").*$"
)
_CLASS_TAIL = re.compile(
    r"(?i)\s+(?:[FM]\s*\d{1,2}|\([FM]\d{0,2}\))\s*$"
)
_DOT_ORDINAL = re.compile(r"\.(?=\d+(?:st|nd|rd|th)\b)", re.I)
_DEGREE_DEG = re.compile(
    r"(?i)\b(\d+(?:st|nd|rd|th)\s+Degree)\s+Deg(?:ree)?\b"
)
_BARE_DEG = re.compile(r"(?i)\b(\d+(?:st|nd|rd|th))\s+Deg\b")
_WITH_SLASH = re.compile(r"(?i)\bw\s*/\s*")
# Jail age shorthand: YOA / years of age → yo (12-16 yoa → 12-16 yo)
_YOA_GLUED = re.compile(r"(?i)(\d)\s*yoa\b")
_YOA_WORD = re.compile(r"(?i)\byoa\b")
_YEARS_OF_AGE = re.compile(r"(?i)\byears?\s+of\s+age\b")
# Furnishing alcohol to under-21 → short plain label.
_ALCOHOL_UNDERAGE = re.compile(
    r"(?i)\b(?:"
    r"(?:selling,?\s*)?(?:giving,?\s*)?(?:or\s+)?(?:serving\s+)?"
    r"alcohol(?:ic)?\s+(?:beverage\s+)?to\s+(?:a\s+)?"
    r"(?:person\s+under\s*21|minor|underage(?:\s+person)?)"
    r"|"
    r"furnish(?:ing)?\s+(?:of\s+)?alcohol(?:ic)?\s+(?:beverage\s+)?"
    r"to\s+(?:a\s+)?(?:minor|person\s+under|underage)"
    r"|"
    r"provid(?:e|ing)\s+alcohol(?:ic)?\s+(?:beverage\s+)?"
    r"to\s+(?:a\s+)?(?:minor|person\s+under|underage)"
    r")\b"
    r"(?:\s*\([^)]*\))?"
)
_SMALL_WORDS = frozenset(
    {
        "a",
        "an",
        "and",
        "of",
        "or",
        "the",
        "to",
        "for",
        "in",
        "on",
        "by",
        "with",
        "yo",  # years old (from yoa) — keep lowercase on cards
    }
)
_AFFIX = re.compile(r"^([(\"'\[]*)(.*?)([.,;:\"'\)\]]*)$")
# Age ranges must keep hyphen (not become charge separators).
_AGE_RANGE = re.compile(r"\b(\d{1,2})\s*[-–—]\s*(\d{1,2})\b")
_AGE_RANGE_TOKEN = "\u0001AGERANGE\u0001"


