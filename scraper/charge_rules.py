"""Compiled charge classification regex rules."""
from __future__ import annotations

import re
from typing import List, Tuple

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
            r"\bindecent\s+(libert|expos|assault|act)",
            r"\bindecency\b", r"\bindency\b",
            r"\blewd\b", r"\blewdness\b", r"\bopen\s+lewd",
            r"\bchild\s+mol", r"\bmolest", r"\bsodomy\b",
            # PA / common: Involuntary Deviate Sexual Intercourse (IDSI)
            r"\binvoluntary\s+deviate\b", r"\bdeviate\s+sexual\s+intercourse\b",
            r"\bdeviatesexual\s+intercourse\b", r"\bidsi\b",
            r"\bsexual\s+intercourse\b", r"\bcarnal\s+knowledge\b",
            r"\bgross\s+sexual\s+imposition\b", r"\bsexual\s+imposition\b",
            r"\bcriminal\s+sexual\s+conduct\b", r"\bcsc\s*\d", r"\bcsc\b",
            r"\bsexual\s+contact\b", r"\babusive\s+sexual\s+contact\b",
            r"\bsexual\s+indecen", r"\bpublic\s+(?:sexual\s+)?indecen",
            r"\bcorruption\s+of\s+(a\s+)?minors?\b",
            r"\bunlawful\s+contact\s+with\s+(a\s+)?minor",
            r"\bvoyeur", r"\bpeeping\b", r"\bbestiality\b", r"\bimportun",
            r"\bcontinuous\s+sexual", r"\bsexual\s+performance\b",
            r"\bstatutory\s+sexual", r"\bsex(?:ual)?\s+seduction\b",
            r"\bsex\s+w/?\s*mnr", r"\bsex(?:ual)?\s+with\s+(a\s+)?min",
            r"\bpornograph", r"\bchild\s+porn", r"\bcsam\b",
            r"\bobscene\s+(?:matter|material)", r"\btransmitting\s+obscene",
            r"\btrans\s*/\s*dstrbtn\s+mat", r"\bmat(?:erial)?\s+dep(?:ict|i)\.?\s*child",
            r"\bprostitution\b", r"\bpatroniz\w*\s+prostitut",
            r"\bsex\s+traffick", r"\bhuman\s+traffick",
            r"\bsolicit\w*\s+.*(sex|prostitu|minor)", r"\bpandering\b",
            r"\bonline\s+solicit(?:ation)?\s+(?:of\s+)?(?:a\s+)?minor",
            r"\bsolicit(?:ation)?\s+(?:of\s+)?(?:a\s+)?(?:minor|child)\b",
            r"\binvasion\s+of\s+privacy.*(sex|intimate)",
            r"\bunlawful\s+sexual", r"\bsexual\s+conduct",
            r"\bforcible\s+fondl", r"\bfondling\b", r"\bfondl",
            r"\bsex\s+crime", r"\bsexually\s+violent",
            r"\bsex(?:ual)?\s+motivat",  # "Sexual Motivation" docket tag
            r"\bfailure\s+to\s+register.*(sex|offender)",
            r"\bsex\s+offender", r"\bregistry.*(sex|offender)",
            r"\benticing\s+a\s+(child|minor)", r"\bluring\s+a\s+minor",
            r"\bcoercion.*(?:sex|force).*sex", r"\bentice\w*.*illegal\s+sexual",
            # Common statute numbers
            r"\b21\.11\b", r"\b3123\b", r"\b288\b", r"\b261(?:\.5)?\b",
            r"\b18\s*usc\s*224[0-9]", r"\b18\s*usc\s*2422",
            r"\b13a-6-11[01]\b", r"\b13a-6-6[0-9]\b",
            r"\b5-14-1[0-9]{2}\b", r"\b200\.368\b", r"\b201\.23\b",
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
            r"\bbreaking\s+and\s+or\s+enter", r"\bbreaking\s+or\s+enter",
            r"\bbreak\s*/\s*enter", r"\bbreak/?enter",
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
            r"\bdomestic\s+assault", r"\bdomestic\s+batter",
            r"\basslt\s+cbi\s+fv\b", r"\bcbi\s+fv\b",
            r"\babuse\s+spousal\b", r"\bspousal\s+abuse\b",
            r"\bbat\s*:\s*spouse", r"\bbattery\s+spouse",
            r"\bchild\s+abuse\b", r"\bchild\s+endanger", r"\bneglect\s+of\s+child",
            r"\belder\s+abuse\b",
            r"\b273\.5\b", r"\bcorp(?:oral)?\s+inj(?:ury)?.{0,20}\b(spouse|cohab)",
            r"\binf\s+corp\s+inj",
        ],
    ),
    (
        "violent",
        [
            r"\bassault\b", r"\bbatter(?:y|ing)\b", r"\baggravated\s+assault",
            r"\bfelonious\s+assault", r"\bstalking\b", r"\bharass",
            r"\bkidnap", r"\bfalse\s+imprison", r"\bunlawful\s+restraint",
            r"\bunl\s+restraint", r"\basslt\b", r"\bstrangul",
            r"\bterroristic\s+threat", r"\bthreat\s+to\s+(kill|injure)",
            r"\bmens?\s+rea.*assault", r"\bmayhem\b", r"\briot\b",
            r"\bresist(ing)?\s+(arrest|officer)", r"\baffray\b",
            r"\bintimidation\b", r"\bmalicious\s+wound",
            r"\btouch\s*(?:or|/|&)\s*strike\b",
            r"\bstrike\s*(?:or|/|&)\s*touch\b",
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
            r"\bdrug\s+equip(?:ment)?", r"\bequip(?:ment)?\s*[-–—/]?\s*possess",
            # Jail shorthand: Man.Delv.Poss Cont Subs
            r"\bman\.?\s*delv", r"\bman(?:ufacture)?\s*/?\s*del(?:iv(?:ery)?)?",
            r"\bposs\.?\s+cont\.?\s+sub", r"\bcont\.?\s+subs?\b",
            r"\bposs\s+cs\b", r"\bposs\s+marij",
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
