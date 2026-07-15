"""Charge summary patterns (_SUMMARY_RULES_A)."""
from __future__ import annotations

from typing import List, Tuple

_SUMMARY_RULES_A: List[Tuple[str, List[str]]] = [
    ('ICE IMMIGRATION HOLD', [
        '\\bice\\b', '\\bi\\.?\\s*c\\.?\\s*e\\.?\\b', '\\bus\\s*immigration\\b', '\\bu\\.?s\\.?\\s*immigration\\b',
        '\\bimmigration\\s+hold\\b', '\\bimmigration\\s+detain', '\\bhold\\s+for\\s+ice\\b',
        '\\bfederal\\s+offense\\s*\\(?\\s*immigration', '\\bimmigration\\b', '\\bins\\s+hold\\b',
        '\\bdhs\\s+hold\\b', '\\bice\\s+detainer\\b', '\\bdetainer\\b', '\\bimmig',
    ]),
    ('FAILURE TO APPEAR', [
        '\\bfta\\b', '\\bfailure\\s+to\\s+appear', '\\bfail(ing)?\\s+to\\s+appear', '\\bfailure\\s+to\\s+(comply|pay)',
        '\\bfta\\s+failure',
    ]),
    ('PROBATION VIOLATION', [
        '\\bprobation\\s+viol', '\\bprobation\\s+revoc', '\\bprobation\\s+revok', '\\bvop\\b',
        '\\bviolation\\s+of\\s+probation',
        '\\bpv\\s*[-–—]?\\s*probation', '\\bobstruction-?\\s*pv\\b.*probation', '\\b15-22-54\\b',
        '\\bparole\\s+viol', '\\bviolation\\s+of\\s+parole', '\\bpv\\s*[-–—]?\\s*parole',
        '\\bconditional\\s+release\\s+viol', '\\b15-18-121\\b',
        '^\\s*pv\\s*$', '^\\s*pv\\s*[-–—/]',
    ]),
    ('DUI', [
        '\\bdui\\b', '\\bdwi\\b', '\\bowi\\b', '\\bovi\\b', '\\bdwui\\b', '\\bd\\.?\\s*u\\.?\\s*i\\.?\\b',
        '\\bdriving\\s+under\\s+(the\\s+)?inf', '\\bdrvg\\s+under\\s+influ', '\\bdriving\\s+while\\s+(intoxic|impair)',
        '\\bimpaired\\s+driving', '\\baggravated\\s+dui', '\\b32-5a-191\\b', '\\b189a\\.?0?10\\b',
        '\\boperat(e|ing)?\\s+.*under\\s+(the\\s+)?influ', '\\boperat(e|ing)?\\s+.*while\\s+intox',
        '\\boperat(e|ing)?\\s+(a\\s+)?(motor\\s+)?vehicle\\s+while\\s+intox', '\\boperat(e|ing)?\\s+while\\s+intox',
        '\\boper(ating)?\\s+(mtr\\s+)?(mv|veh).{0,24}u/?infl', '\\bu/?infl\\b', '\\bunder\\s+the\\s+influence',
        '\\bblood\\s+alcohol', '\\bbac\\b', '\\balc(?:ohol)?\\s*\\.?\\s*0?8\\b', '\\b\\.0?8\\b.*\\balc',
        '\\b(vehicle|motor|driv|operat).{0,40}\\bintox', '\\bintox.{0,40}\\b(vehicle|motor|driv|operat)',
        '\\bboating\\s+while\\s+intox', '\\bphysical\\s+control\\s+of\\s+vehicle\\s+under\\s+influ',
        '\\brefuse\\s+to\\s+submit\\s+to\\s+intox',
    ]),
    ('RECKLESS DRIVING', [
        '\\breckless\\s+driv', '\\bcareless\\s+driv', '\\bwanton\\s+endanger',
    ]),
    ('HIT AND RUN', [
        '\\bhit\\s+and\\s+run', '\\bhit-and-run', '\\bleave\\s+the\\s+scene', '\\bleaving\\s+scene',
    ]),
    ('DRIVING WHILE SUSPENDED', [
        '\\bdriv(ing)?\\s+w(ith)?\\s*(lic|license).*(susp|revok|invalid|barred|cancel)',
        '\\bdriv(ing)?\\s+while\\s+(license|driver|lic).*(susp|revok|invalid|barred)',
        '\\bdriv(ing)?\\s+(on\\s+)?(a\\s+)?susp', '\\bdriv(ing)?\\s+while\\s+(susp|revok|barred)',
        '\\bdriv(ing)?\\s+w/?lic\\s+inv', '\\balias\\s+driving\\s+w\\s+(susp|revok)',
        '\\bsuspended\\s+license', '\\brevoked\\s+license', '\\bno\\s+license\\b', '\\bno\\s+drivers?\\s+license',
        '\\bno\\s+operator', '\\bwithout\\s+ever\\s+obtaining\\s+license', '\\boperating\\s+without\\s+.*license',
        '\\bdriving\\s+under\\s+suspension', '\\bdus\\b', '\\bdwlr\\b', '\\bdriving\\s+after\\s+revocation',
        '\\blicense\\s+invalid', '\\bno\\s+valid\\s+(drivers?\\s+)?license', '\\boperat(e|ing)?\\s+(a\\s+)?(motor\\s+)?vehicle\\s+.*without\\s+.*licen',
        '\\boperat(e|ing)?\\s+.*without\\s+a\\s+valid\\s+licen',
    ]),
    ('EVADING / FLEEING', [
        '\\bevad(e|ing)\\s+arrest', '\\bevad(e|ing)\\s+detention', '\\bevad(e|ing)\\s+arrest\\s+(or\\s+)?det(?:ention)?',
        '\\belud', '\\bfleeing\\b', '\\battempting\\s+to\\s+elude', '\\batepo\\b', '\\bflee/?elude',
    ]),
    ('TRAFFIC OFFENSE', [
        '\\bspeeding\\b', '\\btraffic\\b', '\\buninsured\\b', '\\bno\\s+insurance', '\\bno\\s+proof\\s+of\\s+insurance',
        '\\bfailure\\s+to\\s+produce\\s+insurance', '\\bopen\\s+container', '\\bmv\\s+offense',
        '\\bvehicle\\s+code', '\\bexpired\\s+tag', '\\bregistration\\b', '\\bdistracted\\s+driv',
        '\\bfollowing\\s+too\\s+closely',
    ]),
    ('DOMESTIC VIOLENCE', [
        '\\bdomestic\\s+violence', '\\bdomestice?\\s+violence', '\\bdomestic\\s+assault',
        # AR statutes use "Domestic Battering" (not only "battery")
        '\\bdomestic\\s+batter(?:y|ing)?',
        '\\bfamily\\s+violence', '\\bassault\\s+causes\\s+bodily\\s+injury\\s+family',
        '\\basslt\\s+cbi\\s+fv\\b', '\\bsimple\\s+assault-?family', '\\bharassment-?family',
        '\\bassault-domestic', '\\b13a-6-132\\b', '\\bintimate\\s+partner', '\\bdating\\s+violence',
        '\\bfamily\\s+member', '\\bcorp(?:oral)?\\s+inj(?:ury)?.{0,20}\\b(spouse|cohab)',
        '\\binf\\s+corp\\s+inj', '\\b273\\.5\\b',
    ]),
    ('PROTECTIVE ORDER VIOLATION', [
        '\\bprotect(ive)?\\s+order', '\\brestraining\\s+order', '\\bviol\\s+bond/protect',
        '\\bviolation\\s+of\\s+a\\s+court\\s+order', '\\bviolat.*(protect|restrain|court\\s+order)',
    ]),
    ('CHILD ABUSE / ENDANGERMENT', [
        '\\bchild\\s+abuse', '\\bchild\\s+endanger', '\\bneglect\\s+of\\s+child', '\\bendanger(ing)?\\s+the\\s+welfare\\s+of\\s+a\\s+minor',
        '\\bendanger(ing)?\\s+.*\\bminor\\b', '\\bwelfare\\s+of\\s+a\\s+minor', '\\bchild\\s+support',
    ]),
    ('SEX OFFENSE', [
        '\\bsexual\\s+assault\\b', '\\bsexual\\s+asslt\\b', '\\bsex\\s+asslt\\b', '\\bsex\\s+assault\\b',
        '\\brape\\b', '\\bsex\\s+offense', '\\bsexual\\s+abuse', '\\bsexual\\s+battery',
        '\\bsexual\\s+misconduct', '\\bsexual\\s+conduct', '\\bsexual\\s+solicitation',
        '\\bsexual\\s+exploit', '\\bsex(?:ual)?\\s+penetrat', '\\boral\\s+copulat',
        '\\bcarnal\\s+abuse', '\\bincest\\b', '\\bsodomy\\b', '\\bchild\\s+mol', '\\bmolest', '\\blewd\\b',
        '\\bindecent\\s+', '\\bpornograph', '\\bchild\\s+porn', '\\bobscene\\s+matter',
        '\\bprostitution\\b', '\\bsex\\s+traffick', '\\bsex\\s+offender', '\\bfailure\\s+to\\s+register.*(sex|offender)',
        '\\bunlawful\\s+sexual', '\\bfondl', '\\benticing\\s+a\\s+child', '\\belectronic\\s+solicitation',
        '\\bengage\\s+child\\s+in\\s+sex', '\\bluring\\s+a\\s+minor', '\\bsex\\s+act.*student',
        '\\bdeviant\\s+sexual', '\\bharmful\\s+matter.*minor', '\\bviolation\\s+of\\s+a\\s+minor',
        '\\b13a-6-6[1-9]\\b', '\\b13a-6-12[0-9]\\b', '\\b13a-6-81\\b', '\\b13a-13-3\\b',
        '\\b13-1405\\b', '\\b13-3553\\b', '\\b13-3554\\b',
    ]),
    ('HOMICIDE / MURDER', [
        '\\bmurder\\b', '\\bhomicide\\b', '\\bmanslaughter\\b',
    ]),
]
