"""Charge summary patterns part B (weapons through public order)."""
from __future__ import annotations
from typing import List, Tuple
_SUMMARY_RULES_B: List[Tuple[str, List[str]]] = [
    (
        "KIDNAPPING / FALSE IMPRISONMENT",
        [
            r"\bkidnap",
            r"\bfalse\s+imprison",
            r"\bunlawful\s+restraint",
            r"\bunl\s+restraint",
            r"\bcriminal\s+restraint",
        ],
    ),
    (
        "STALKING / HARASSMENT",
        [r"\bstalking\b", r"\bharass", r"\bintimidation\b", r"\bharassing\s+communications"],
    ),
    (
        "RESISTING ARREST",
        [
            r"\bresist(ing)?\s+(arrest|officer)",
            r"\bresist(ing)?\s+officer\s+without\s+violence",
            r"\bobstruct(ing)?\s+(officer|police)",
        ],
    ),
    # --- Drugs before weapons so "cannabis with a weapon" is still marijuana ---
    (
        "DRUG TRAFFICKING / DISTRIBUTION",
        [r"\bdrug\s+traffick", r"\btraffick.*drug", r"\bintent\s+to\s+(distrib|deliver|sell)", r"\bdelivery\s+of\b", r"\bpwid\b", r"\bmanufacture.*controlled"],
    ),
    (
        "POSSESSION OF MARIJUANA",
        [r"\bposs(ession)?\s+of\s+marij", r"\bmarijuana\b", r"\bcannabis\b", r"\bpom\b", r"\b13a-12-213\b"],
    ),
    (
        "POSSESSION OF METHAMPHETAMINE",
        [r"\bmeth(amphetamine)?\b", r"\bmethamphetamine-?possess"],
    ),
    (
        "DRUG PARAPHERNALIA",
        [r"\bparaphernalia\b", r"\buse/possession\s+drug\s+paraphernalia", r"\b13a-12-260\b"],
    ),
    (
        "POSSESSION OF CONTROLLED SUBSTANCE",
        [r"\bcontroll?ed\s+substance", r"\bpossession\s+of\s+controlled", r"\bunlawful\s+possession\s+controlled", r"\bposs(ession)?\s+of\s+dangerous\s+drugs", r"\bpossession\s+of\s+a\s+controlled", r"\bposs\s+cs\b", r"\bposs(ess|ession)?/?receive\s+cont", r"\bcocaine\b", r"\bheroin\b", r"\bfentanyl\b", r"\bnarcotic", r"\bcds\b", r"\b13a-12-212\b", r"\bdangerous\s+drugs\b"],
    ),
    # --- Theft before weapons so "grand theft … firearm" is theft ---
    (
        "BURGLARY / B&E",
        [r"\bburglar", r"\bb\s*&\s*e\b", r"\bbreaking\s+and\s+enter", r"\bhome\s+invasion", r"\bunlawful\s+entry"],
    ),
    (
        "THEFT / LARCENY",
        [r"\btheft\s+of\s+property", r"\bgrand\s+theft", r"\bpetit\s+theft", r"\bpetty\s+theft", r"\btheft\b", r"\blarceny\b", r"\bshoplift", r"\bstolen\s+propert", r"\breceiv(ing|ed)\s+stolen", r"\bmotor\s+vehicle\s+theft", r"\bauto\s+theft", r"\bunlawful\s+taking"],
    ),
    # --- Weapons ---
    (
        "WEAPONS OFFENSE",
        [r"\bfirearm", r"\bhandgun\b", r"\brifle\b", r"\bshotgun\b", r"\bweapon", r"\bconcealed\s+carry", r"\bammunition\b", r"\bbrandish", r"\bdeadly\s+weapon", r"\bexplosive"],
    ),
    (
        "CRIMINAL TRESPASS",
        [r"\btrespass", r"\bcriminal\s+trespass"],
    ),
    (
        "CRIMINAL MISCHIEF / VANDALISM",
        [r"\bvandal", r"\bcriminal\s+mischief", r"\bproperty\s+damage", r"\barson\b"],
    ),
    # --- Fraud ---
    (
        "FRAUD / FORGERY / ID THEFT",
        [r"\bfraud\b", r"\bforgery\b", r"\bidentity\s+theft", r"\bid\s+theft", r"\bembezzl", r"\bcounterfeit", r"\bcredit\s+card", r"\bbad\s+check", r"\bmoney\s+launder", r"\bextortion\b", r"\bbribery\b"],
    ),
    # --- Holds / warrants / court ---
    (
        "HOLD FOR OTHER AGENCY",
        [
            r"\bhold\s+for\s+(another|other)\s+agency",
            r"\bhold\s+for\s+agency",
            r"\bhold\s+for\s+[a-z].*county",
            r"\bhold\s+for\s+[a-z]",
            r"\bout\s+of\s+county\s+hold",
            r"\bout\s+of\s+county\s+warrant",
            r"\bout\s+of\s+county\s*/",  # OUT OF COUNTY/…
            r"\bout\s+of\s+county\b",
            r"\bcourtesy\s+hold",
            r"\bhousing\s+for\b",
            r"\bhold\s+for\s+usms\b",
            r"\bhold\s+for\s+transport",
            r"\btemporary\s+hold\b",
            r"\b24\s*hour\s+hold",
            r"\bcourt\s+order\s+hold",
            r"\bhold\b$",
            r"^hold\b",
        ],
    ),
    (
        "BENCH WARRANT / ALIAS WRIT",
        [r"\bbench\s+warrant", r"\balias\s+writ", r"\bwarrant\b", r"\b15-10-60\b", r"\bpublic\s+order\s+crimes-?aw"],
    ),
    (
        "FAILURE TO IDENTIFY",
        [
            r"\bfail(ure)?\s+to\s+id\b",
            r"\bfail(ure)?\s+to\s+identify",
            r"\bfail\s+to\s+id\s+fugitive",
            r"\brefuse\s+to\s+give\b",
        ],
    ),
    (
        "ORGANIZED CRIMINAL ACTIVITY",
        [
            r"\borganized\s+criminal\s+activity",
            r"\bengaging\s+in\s+organized",
            r"\beoca\b",
        ],
    ),
    (
        "FUGITIVE FROM JUSTICE",
        [r"\bfugitive\s+from\s+justice", r"\bfugitive\b"],
    ),
    (
        "CONTEMPT OF COURT",
        [r"\bcontempt\b", r"\bcourt\s+order\b", r"\border\s+of\s+commitment"],
    ),
    (
        "BAIL JUMPING / BOND VIOLATION",
        [r"\bbail\s+jump", r"\bbond\s+revok", r"\bviol\s+bond", r"\b13a-10-39\b"],
    ),
    (
        "PUBLIC INTOXICATION",
        [r"\bpublic\s+intoxic", r"\bdrunk\s+in\s+public", r"\bappears\s+in\s+public\s+place\s+under\s+influence", r"\balcohol\s+intoxication\s+in\s+a\s+public"],
    ),
    (
        "DISORDERLY CONDUCT",
        [r"\bdisorderly\b", r"\bloitering\b", r"\baffray\b", r"\briot\b"],
    ),
    (
        "ESCAPE / JAIL OFFENSE",
        [r"\bescape\b", r"\bserving\s+time", r"\bsentence\s+to\s+serve", r"\breturn\s+for\s+court"],
    ),
    (
        "OBSTRUCTION OF JUSTICE",
        [r"\bobstruct(ing)?\s+justice", r"\bfalse\s+report", r"\bperjury\b", r"\bfailure\s+to\s+obey"],
    ),
]
