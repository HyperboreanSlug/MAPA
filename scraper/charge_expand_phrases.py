"""Phrase substitutions for jail booking charge expansion (longest first)."""
from __future__ import annotations

from typing import List, Tuple

# Applied case-insensitively before per-token expansion.
EXPAND_PHRASES: List[Tuple[str, str]] = [
    # NC-style break/enter + assault on LE/probation/parole
    (
        r"\bBREAK\s*/\s*ENTER(?:ING)?\s+(?:OF\s+)?MOTOR\s+VEH(?:ICLE)?\s+W\s*/\s*THEFT\b",
        "Breaking and Entering a Motor Vehicle With Theft",
    ),
    (
        r"\bBREAK\s*/\s*ENTER(?:ING)?\s+(?:OF\s+)?MOTOR\s+VEH(?:ICLE)?\b",
        "Breaking and Entering a Motor Vehicle",
    ),
    (
        r"\bBREAK(?:ING)?\s*(?:/|OR)\s*ENTER(?:ING)?\b",
        "Breaking and Entering",
    ),
    (
        r"\bASSAULT\s+PHY(?:SICAL)?\s+INJ(?:URY)?\s+LE\s*/\s*PROB\s*/\s*PAR(?:OLE)?\s+OF\b",
        "Assault Causing Physical Injury to a Law Enforcement, Probation, or Parole Officer",
    ),
    (
        r"\bASSAULT\s+PHY(?:SICAL)?\s+INJ(?:URY)?\b",
        "Assault Causing Physical Injury",
    ),
    (
        r"\bRESISTING\s+PUBLIC\s+OFFICER\b",
        "Resisting a Public Officer",
    ),
    (
        r"\bAGG\s+ASSAULT\s+DATE\s*/\s*FAMILY\s*/\s*HOUSE(?:HOLD)?\s+W\s*/\s*WEAPON\s+SBI\b",
        "Aggravated Assault on Dating, Family, or Household Member With Weapon Causing Serious Bodily Injury",
    ),
    (
        r"\bDATE\s*/\s*FAMILY\s*/\s*HOUSE(?:HOLD)?\b",
        "Dating, Family, or Household Member",
    ),
    (
        r"\bLE\s*/\s*PROB\s*/\s*PAR(?:OLE)?\b",
        "Law Enforcement, Probation, or Parole",
    ),
    (r"\bMOTOR\s+VEH(?:ICLE)?\b", "Motor Vehicle"),
    (r"\bVEH(?:ICLE)?\s+THEFT\b", "Vehicle Theft"),
    (r"\bW\s*/\s*THEFT\b", "With Theft"),
    (r"\bW\s*/\s*WEAPON\b", "With Weapon"),
    (r"\bW\s*/\s*DEADLY\s+WEAPON\b", "With Deadly Weapon"),
    (r"\bUNAUTH(?:ORIZED)?\s+USE\s+OF\s+(?:A\s+)?VEHICLE\b", "Unauthorized Use of a Vehicle"),
    (r"\bPOSS\s+CONT(?:ROLLED)?\s+SUB(?:STANCE)?\b", "Possession of Controlled Substance"),
    (r"\bPOSS\s+OF\s+MARIJUANA\b", "Possession of Marijuana"),
    (r"\bDRUG\s+PARAPHERNALIA\s*[-–—]?\s*BUY\s*/\s*POSSESS\b", "Possession of Drug Paraphernalia"),
    (r"\bUSE\s*/\s*POSSESSION\s+DRUG\s+PARAPHERNALIA\b", "Possession of Drug Paraphernalia"),
    (r"\bDRUG\s+EQUIP(?:MENT)?\s*[-–—/]?\s*POSSESS(?:ION)?\b", "Possession of Drug Equipment"),
    (r"\bPOSS(?:ESS(?:ION)?)?\s+(?:OF\s+)?DRUG\s+EQUIP(?:MENT)?\b", "Possession of Drug Equipment"),
    (r"\bFAILURE\s+TO\s+APPEAR\s*/\s*COMPLY\s*/\s*PAY\b", "Failure to Appear, Comply, or Pay"),
    (r"\bANNOY\s*/\s*MOLEST\b", "Annoy or Molest"),
    (r"\bSEND\s*/\s*SELL\s*/\s*DISTRIBUTE\b", "Send, Sell, or Distribute"),
    (r"\bPOSSESS\s*/\s*RECEIVE\b", "Possess or Receive"),
    (r"\bPOSSESS\s*/\s*CONTROL\b", "Possess or Control"),
    (r"\bSUSPENDED\s*/\s*REVOKED\b", "Suspended or Revoked"),
    (r"\bREVOKED\s*/\s*SUSPENDED\b", "Revoked or Suspended"),
    # Existing Texas / common jail shorthand
    (r"\bONLINE\s+SOLICIT(?:ATION)?\s+(?:OF\s+)?(?:A\s+)?MINOR\b", "Online Solicitation of a Minor"),
    (r"\bSOLICIT(?:ATION)?\s+(?:OF\s+)?(?:A\s+)?MINOR\b", "Solicitation of a Minor"),
    (r"\bTOUCH\s*(?:OR|/|&)\s*STRIKE\b", "Battery (Touch or Strike)"),
    (r"\bSTRIKE\s*(?:OR|/|&)\s*TOUCH\b", "Battery (Touch or Strike)"),
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
    (r"\bPHY(?:SICAL)?\s+INJ(?:URY)?\b", "Physical Injury"),
    (r"\bDOM\s+ASSLT\b", "Domestic Assault"),
    (r"\bDOMESTIC\s+ASSLT\b", "Domestic Assault"),
    (r"\bSIMPLE\s+ASSLT\b", "Simple Assault"),
    (r"\bSMPL\s+ASSLT\b", "Simple Assault"),
    (r"\bSEX\s+ASSLT\b", "Sexual Assault"),
    (r"\bVIOL\s+BOND/?PROTECT(?:IVE)?\s+ORDER\b", "Violation of Bond or Protective Order"),
    (r"\bDRIVING\s+WHILE\s+INTOXICATED\b", "Driving While Intoxicated"),
    (r"\bFAILURE\s+TO\s+APPEAR\b", "Failure to Appear"),
    (
        r"\bEVADING\s+ARREST(?:\s+(?:OR\s+)?DET(?:ENTION)?)?(?:\s+W/?\s*VEH(?:ICLE)?)?\b",
        "Evading Arrest",
    ),
    (r"\bFAIL(?:URE)?\s+TO\s+ID(?:ENTIFY)?\b", "Failure to Identify"),
    (r"\bFUGITIVE\s+FRM\s+JUSTICE\b", "Fugitive from Justice"),
    (
        r"\bENGAGING\s+IN\s+ORGANIZED\s+CRIMINAL\s+ACTIVITY\b",
        "Engaging in Organized Criminal Activity",
    ),
    (r"\bMTR\s*[-–—:]\s*", ""),
    (r"\bMTR\s+(?=ENGAGING|EVADING|FAIL|POSS|ASSAULT|THEFT|SEXUAL)", ""),
    (r"\bSEXUAL\s+ASSLT\b", "Sexual Assault"),
    (
        r"\bOPER(?:ATING)?\s+(?:MTR\s+)?(?:MV|VEH(?:ICLE|ICAL)?)\s+U/?INFL(?:UENCE)?"
        r"(?:\s+(?:OF\s+)?(?:ALC(?:OHOL)?|SUBST(?:ANCE)?))?",
        "Operating Motor Vehicle Under the Influence",
    ),
    (r"\bU/?INFL(?:UENCE)?(?:\s+(?:ALC(?:OHOL)?|SUBST(?:ANCE)?))?\b", "Under the Influence"),
    (r"\bNO\s+OPERATOR'?S?(?:/MOPED)?\s+LICENSE\b", "No Operator License"),
    (r"\bFLEE/?ELUDE\b", "Flee or Elude"),
    (r"\bRESISTING\s+OFFICER\s+WITHOUT\s+VIOLENCE\b", "Resisting Officer Without Violence"),
    (
        r"\bPOSS\.?\s+OF\s+WEAPON\s+IN\s+COMMISSION\s+OF\s+FELONY\b",
        "Possession of Weapon in Commission of Felony",
    ),
    (r"\bGRAND\s+THEFT\s+3RD\s+DEGREE[-\s]?FIREARM\b", "Grand Theft Firearm"),
    # Ordinal degree glued to digits
    (r"\b(\d+)(?:ST|ND|RD|TH)\s+DEGREE\b", r"\1th Degree"),
]
