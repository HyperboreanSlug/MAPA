"""Expand jail booking abbreviations into full plain-language charges."""
from __future__ import annotations

import re
from typing import Any, List, Tuple

_PHRASES: List[Tuple[str, str]] = [
    (r"\bASSLT\s+CBI\s+FV\b", "Assault Causes Bodily Injury Family Violence"),
    (r"\bASSLT\s+CBI\b", "Assault Causes Bodily Injury"),
    (r"\bAGG\s+ASSLT\b", "Aggravated Assault"),
    (r"\bAGG\s+ASSAULT\b", "Aggravated Assault"),
    (r"\bUNL\s+RESTRAINT\s+FV\b", "Unlawful Restraint Family Violence"),
    (r"\bUNL\s+RESTRAINT\b", "Unlawful Restraint"),
    (r"\bUNLAWFUL\s+RESTRAINT\b", "Unlawful Restraint"),
    (r"\bUNL\s+CARRYING\s+WEAPON\b", "Unlawful Carrying Weapon"),
    (r"\bUNL\s+POSS\s+FIREARM\b", "Unlawful Possession of Firearm"),
    (r"\bPOSS\s+CS\b", "Possession of Controlled Substance"),
    (r"\bPOSS\s+MARIJ\b", "Possession of Marijuana"),
    (r"\bMAN\s*DEL\s+CS\b", "Manufacture or Delivery of Controlled Substance"),
    (r"\bW/?DEADLY\s+WEAPON\b", "With Deadly Weapon"),
    (r"\bW/?WEAPON\b", "With Weapon"),
    (r"\bSERIOUS\s+BODILY\s+INJ(?:URY|RY)?\b", "Serious Bodily Injury"),
    (r"\bBODILY\s+INJ(?:URY|RY)?\b", "Bodily Injury"),
    (r"\bDOM\s+ASSLT\b", "Domestic Assault"),
    (r"\bDOMESTIC\s+ASSLT\b", "Domestic Assault"),
    (r"\bSIMPLE\s+ASSLT\b", "Simple Assault"),
    (r"\bSMPL\s+ASSLT\b", "Simple Assault"),
    (r"\bSEX\s+ASSLT\b", "Sexual Assault"),
    (r"\bVIOL\s+BOND/?PROTECT(?:IVE)?\s+ORDER\b", "Violation of Bond or Protective Order"),
    (r"\bDRIVING\s+WHILE\s+INTOXICATED\b", "Driving While Intoxicated"),
    (r"\bFAILURE\s+TO\s+APPEAR\b", "Failure to Appear"),
    (r"\bEVADING\s+ARREST(?:\s+(?:OR\s+)?DET(?:ENTION)?)?(?:\s+W/?\s*VEH(?:ICLE)?)?\b", "Evading Arrest"),
    (r"\bFAIL(?:URE)?\s+TO\s+ID(?:ENTIFY)?\b", "Failure to Identify"),
    (r"\bFUGITIVE\s+FRM\s+JUSTICE\b", "Fugitive from Justice"),
    (r"\bENGAGING\s+IN\s+ORGANIZED\s+CRIMINAL\s+ACTIVITY\b", "Engaging in Organized Criminal Activity"),
    (r"(?i)\bMTR\s*[-–—:]\s*", ""),
    (r"\bMTR\s+(?=ENGAGING|EVADING|FAIL|POSS|ASSAULT|THEFT|SEXUAL)", ""),
    (r"(?i)\bSEXUAL\s+ASSLT\b", "Sexual Assault"),
    (r"\bOPER(?:ATING)?\s+(?:MTR\s+)?(?:MV|VEH(?:ICLE|ICAL)?)\s+U/?INFL(?:UENCE)?(?:\s+(?:OF\s+)?ALC(?:OHOL)?)?", "Operating Motor Vehicle Under the Influence of Alcohol"),
    (r"\bU/?INFL(?:UENCE)?(?:\s+ALC(?:OHOL)?)?\b", "Under the Influence of Alcohol"),
    (r"\bNO\s+OPERATOR'?S?(?:/MOPED)?\s+LICENSE\b", "No Operator License"),
    (r"\bFLEE/?ELUDE\b", "Flee or Elude"),
    (r"\bRESISTING\s+OFFICER\s+WITHOUT\s+VIOLENCE\b", "Resisting Officer Without Violence"),
    (r"\bPOSS\.?\s+OF\s+WEAPON\s+IN\s+COMMISSION\s+OF\s+FELONY\b", "Possession of Weapon in Commission of Felony"),
    (r"\bGRAND\s+THEFT\s+3RD\s+DEGREE[-\s]?FIREARM\b", "Grand Theft Firearm"),
]

# Whole-token map (applied after phrases). Keys are uppercase.
_TOKENS = {
    "ASSLT": "Assault",
    "AGG": "Aggravated",
    "AGGRAV": "Aggravated",
    "CBI": "Causes Bodily Injury",
    "SBI": "Serious Bodily Injury",
    "FV": "Family Violence",
    "UNL": "Unlawful",
    "POSS": "Possession",
    "CS": "Controlled Substance",
    "MARIJ": "Marijuana",
    "MARIJUANA": "Marijuana",
    "FTA": "Failure to Appear",
    "FRM": "From",
    "DWI": "Driving While Intoxicated",
    "DUI": "Driving Under the Influence",
    "OWI": "Operating While Intoxicated",
    "OVI": "Operating a Vehicle Impaired",
    "PG": "Penalty Group",
    "DOM": "Domestic",
    "VIOL": "Violation",
    "PROTECT": "Protective",
    "PROTECTIVE": "Protective",
    "RESTRAINT": "Restraint",
    "WEAPON": "Weapon",
    "WEAPONS": "Weapons",
    "FIREARM": "Firearm",
    "FELON": "Felon",
    "DEADLY": "Deadly",
    "BODILY": "Bodily",
    "INJ": "Injury",
    "INJRY": "Injury",
    "INJURY": "Injury",
    "FAMILY": "Family",
    "MEMBER": "Member",
    "ASSAULT": "Assault",
    "BATTERY": "Battery",
    "SEX": "Sexual",
    "SEXUAL": "Sexual",
    "ATT": "Attempted",
    "ATTEMPTED": "Attempted",
    "EVADING": "Evading",
    "ARREST": "Arrest",
    "DETENTION": "Detention",
    "THEFT": "Theft",
    "CRIMINAL": "Criminal",
    "MISCHIEF": "Mischief",
    "RESIST": "Resisting",
    "RESISTING": "Resisting",
    "OBSTRUCT": "Obstructing",
    "LEO": "Law Enforcement Officer",
    "SMPL": "Simple",
    "SIMPLE": "Simple",
    "INTOXICATED": "Intoxicated",
    "INTOX": "Intoxicated",
    "OPEN": "Open",
    "ALCH": "Alcohol",
    "CONTAINER": "Container",
    "MAN": "Manufacture",
    "DEL": "Delivery",
    "PROH": "Prohibited",
    "PROHIBITED": "Prohibited",
    "BOND": "Bond",
    "ORDER": "Order",
    "COURT": "Court",
    "WARR": "Warrant",
    "WARRANT": "Warrant",
    "BENCH": "Bench",
    "FUGITIVE": "Fugitive",
    "JUSTICE": "Justice",
    "PAROLE": "Parole",
    "PROBATION": "Probation",
    "HOLD": "Hold",
    "ICE": "Immigration and Customs Enforcement",
    "IMMIGRATION": "Immigration",
}

# Class letter at segment start: A/B/C misdemeanor, F felony.
_CLASS_PREFIX = re.compile(
    r"^\s*([ABC])\s+(?=[A-Za-z])",
    re.IGNORECASE,
)
_FELONY_PREFIX = re.compile(r"^\s*F\s+(?=[A-Za-z])", re.IGNORECASE)
_SPLIT = re.compile(r"\s*[;|]\s*")
_WORD = re.compile(r"[A-Za-z][A-Za-z'/.-]*|\d+(?:\.\d+)?|[^\s]")

def _expand_segment(segment: str) -> str:
    s = " ".join((segment or "").replace("\u00a0", " ").split())
    if not s:
        return ""
    class_note = ""
    m = _CLASS_PREFIX.match(s)
    if m:
        class_note = f"Class {m.group(1).upper()} Misdemeanor "
        s = s[m.end() :]
    else:
        m = _FELONY_PREFIX.match(s)
        if m:
            class_note = "Felony "
            s = s[m.end() :]
    for pat, repl in _PHRASES:
        s = re.sub(pat, repl, s, flags=re.IGNORECASE)
    parts: List[str] = []
    for tok in _WORD.findall(s):
        key = tok.upper().rstrip(".")
        if key in _TOKENS:
            parts.append(_TOKENS[key])
        elif tok.isalpha() and tok.isupper() and len(tok) <= 4 and key not in _TOKENS:
            # Unknown short jail code: spell out letter-by-letter only if 1 char
            parts.append(tok.title() if len(tok) > 1 else tok.upper())
        else:
            parts.append(tok if not tok.isalpha() else tok.title())
    out = re.sub(r"\s+", " ", " ".join(parts)).strip(" ,.;:-")
    out = re.sub(r"\b(With)\s+\1\b", r"\1", out, flags=re.IGNORECASE)
    return (class_note + out).strip()

def expand_charge_text(text: str) -> str:
    """Expand abbreviations in raw charge text; keep multi-charge separators."""
    from scraper.charge_sanitize import is_non_charge, sanitize_charge_text

    raw = sanitize_charge_text(" ".join((text or "").replace("\u00a0", " ").split()))
    if not raw or is_non_charge(raw):
        return ""
    segs = [p for p in _SPLIT.split(raw) if p and p.strip()] or [raw]
    expanded = [e for e in (_expand_segment(p) for p in segs) if e and not is_non_charge(e)]
    return "; ".join(expanded)

def expand_charge(record_or_text: Any) -> str:
    """Full plain-language charge for details and export cards."""
    from scraper.charge_recover import recover_charge_from_record

    if record_or_text is None:
        return "—"
    if isinstance(record_or_text, dict):
        parts = [
            record_or_text.get(k)
            for k in (
                "charge_description",
                "charge_group",
                "offense",
                "offense_description",
                "statute",
            )
        ]
        blob = " | ".join(str(p) for p in parts if p and str(p).strip())
        out = expand_charge_text(blob)
        if out:
            return out
        recovered = recover_charge_from_record(record_or_text)
        return expand_charge_text(recovered) if recovered else "—"
    return expand_charge_text(str(record_or_text)) or "—"
