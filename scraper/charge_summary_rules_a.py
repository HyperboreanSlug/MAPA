"""Charge summary patterns part A (through violent)."""
from __future__ import annotations
from typing import List, Tuple
_SUMMARY_RULES_A: List[Tuple[str, List[str]]] = [
    # --- Immigration / ICE ---
    (
        "ICE IMMIGRATION HOLD",
        [r"\bice\b", r"\bus\s*immigration\b", r"\bu\.?s\.?\s*immigration\b", r"\bimmigration\s+hold\b", r"\bimmigration\s+detain", r"\bhold\s+for\s+ice\b", r"\bfederal\s+offense\s*\(?\s*immigration", r"\bimmigration\b", r"\bins\s+hold\b", r"\bdhs\s+hold\b", r"\bice\s+detainer\b", r"\bdetainer\b.*\b(ice|immig)", r"\bimmig"],
    ),
    # --- Failure to appear ---
    (
        "FAILURE TO APPEAR",
        [r"\bfta\b", r"\bfailure\s+to\s+appear", r"\bfail(ing)?\s+to\s+appear", r"\bfailure\s+to\s+(comply|pay)", r"\bfta\s+failure"],
    ),
    # --- Probation / parole ---
    (
        "PROBATION VIOLATION",
        [r"\bprobation\s+viol", r"\bprobation\s+revoc", r"\bvop\b", r"\bviolation\s+of\s+probation", r"\bpv\s*[-–—]?\s*probation", r"\bobstruction-?\s*pv\b.*probation", r"\b15-22-54\b"],
    ),
    (
        "PAROLE VIOLATION",
        [r"\bparole\s+viol", r"\bviolation\s+of\s+parole", r"\bpv\s*[-–—]?\s*parole", r"\bobstruction-?\s*pv\b.*parole"],
    ),
    (
        "CONDITIONAL RELEASE VIOLATION",
        [r"\bconditional\s+release\s+viol", r"\b15-18-121\b"],
    ),
    # --- DUI / traffic impairment ---
    (
        "DUI / DWI",
        [
            r"\bdui\b",
            r"\bdwi\b",
            r"\bowi\b",
            r"\bovi\b",
            r"\bd\.?\s*u\.?\s*i\.?\b",
            r"\bdriving\s+under\s+the\s+inf",
            r"\bdriving\s+while\s+(intoxic|impair)",
            r"\bimpaired\s+driving",
            r"\baggravated\s+dui",
            r"\b32-5a-191\b",
            r"\b189a\.?0?10\b",  # KY DUI statute
            r"\boperating\s+.*under\s+influence",
            r"\boper(ating)?\s+(mtr\s+)?(mv|veh)",  # OPER MV …
            r"\bu/?infl\b",  # U/INFL, UINFL
            r"\bunder\s+the\s+influence",
            r"\bblood\s+alcohol",
            r"\bbac\b",
            r"\balc(?:ohol)?\s*\.?\s*0?8\b",  # ALC .08
            r"\b\.0?8\b.*\balc",
        ],
    ),
    (
        "RECKLESS DRIVING",
        [r"\breckless\s+driv"],
    ),
    (
        "HIT AND RUN",
        [r"\bhit\s+and\s+run", r"\bleave\s+the\s+scene"],
    ),
    (
        "DRIVING WHILE SUSPENDED / REVOKED",
        [
            r"\bdriv(ing)?\s+w(ith)?\s*(lic|license).*(susp|revok)",
            r"\bdriv(ing)?\s+while\s+(license|driver).*(susp|revok)",
            r"\balias\s+driving\s+w\s+(susp|revok)",
            r"\bsuspended\s+license",
            r"\brevoked\s+license",
            r"\bno\s+license\b",
            r"\bno\s+operator",
            r"\bwithout\s+ever\s+obtaining\s+license",
            r"\boperating\s+without\s+.*license",
        ],
    ),
    (
        # Texas booking: EVADING ARREST DET W/VEH → short label (before generic eluding)
        "EVADING ARREST",
        [
            r"\bevad(e|ing)\s+arrest",
            r"\bevad(e|ing)\s+detention",
            r"\bevad(e|ing)\s+arrest\s+(or\s+)?det(?:ention)?",
            r"\bevad(e|ing)\s+arrest\s+det\b",
        ],
    ),
    (
        "ELUDING / FLEEING",
        [
            r"\belud",
            r"\bfleeing\b",
            r"\battempting\s+to\s+elude",
            r"\batepo\b",
            r"\bflee/?elude",
        ],
    ),
    (
        "TRAFFIC OFFENSE",
        [r"\bspeeding\b", r"\btraffic\b", r"\buninsured\b", r"\bopen\s+container", r"\bmv\s+offense", r"\bvehicle\s+code"],
    ),
    # --- Domestic / family ---
    (
        "DOMESTIC VIOLENCE",
        [
            r"\bdomestic\s+violence",
            r"\bdomestice?\s+violence",
            r"\bdomestic\s+assault",
            r"\bdomestic\s+battery",
            r"\bfamily\s+violence",
            r"\bassault\s+causes\s+bodily\s+injury\s+family",
            r"\basslt\s+cbi\s+fv\b",
            r"\bsimple\s+assault-?family",
            r"\bharassment-?family",
            r"\bassault-domestic",
            r"\b13a-6-132\b",
            r"\bintimate\s+partner",
        ],
    ),
    (
        "PROTECTIVE / RESTRAINING ORDER VIOLATION",
        [r"\bprotect(ive)?\s+order", r"\brestraining\s+order", r"\bviol\s+bond/protect", r"\bviolation\s+of\s+a\s+court\s+order", r"\bviolat.*(protect|restrain|court\s+order)"],
    ),
    (
        "CHILD ABUSE / ENDANGERMENT",
        [
            r"\bchild\s+abuse",
            r"\bchild\s+endanger",
            r"\bneglect\s+of\s+child",
            r"\bendanger(ing)?\s+the\s+welfare\s+of\s+a\s+minor",
            r"\bendanger(ing)?\s+.*\bminor\b",
            r"\bwelfare\s+of\s+a\s+minor",
        ],
    ),
    # --- Sex crimes (specific labels first) ---
    (
        "SEXUAL ASSAULT",
        [
            r"\bsexual\s+assault\b",
            r"\bsexual\s+asslt\b",
            r"\bsex\s+asslt\b",
            r"\bsex\s+assault\b",
        ],
    ),
    (
        "SEX OFFENSE",
        [
            r"\brape\b",
            r"\bsex\s+offense",
            r"\bsexual\s+abuse",
            r"\bsexual\s+battery",
            r"\bchild\s+mol",
            r"\bmolest",
            r"\blewd\b",
            r"\bindecent\s+",
            r"\bpornograph",
            r"\bchild\s+porn",
            r"\bprostitution\b",
            r"\bsex\s+traffick",
            r"\bsex\s+offender",
            r"\bfailure\s+to\s+register.*(sex|offender)",
            r"\bunlawful\s+sexual",
            r"\bfondl",
        ],
    ),
    # --- Homicide / violent ---
    (
        "HOMICIDE / MURDER",
        [r"\bmurder\b", r"\bhomicide\b", r"\bmanslaughter\b"],
    ),
    (
        "ROBBERY",
        [r"\brobbery\b", r"\bcarjack", r"\bstrong.?arm"],
    ),
    (
        "ASSAULT / BATTERY",
        [r"\baggravated\s+assault", r"\bfelonious\s+assault", r"\bsimple\s+assault", r"\bassault\b", r"\bbattery\b", r"\bstrangul", r"\bterroristic\s+threat", r"\bthreat\s+to\s+(kill|injure)", r"\bmalicious\s+wound", r"\bmayhem\b"],
    ),
]
