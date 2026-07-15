"""Charge summary patterns (_SUMMARY_RULES_C)."""
from __future__ import annotations

from typing import List, Tuple

_SUMMARY_RULES_C: List[Tuple[str, List[str]]] = [
    ('CRIMINAL MISCHIEF / VANDALISM', [
        '\\bvandal', '\\bcriminal\\s+mischief', '\\bproperty\\s+damage', '\\barson\\b',
    ]),
    ('FRAUD / FORGERY / ID THEFT', [
        '\\bfraud\\b', '\\bforgery\\b', '\\bidentity\\s+theft', '\\bid\\s+theft', '\\bembezzl',
        '\\bcounterfeit', '\\bcredit\\s+card', '\\bbad\\s+check', '\\bmoney\\s+launder',
        '\\bextortion\\b', '\\bbribery\\b', '\\bfalse\\s+(id|identification|info|inform)',
        '\\bgiving\\s+false\\s+id',
    ]),
    ('HOLD FOR OTHER AGENCY', [
        # "Holding" (gerund) is common on dockets; match hold/holding/held
        '\\bhold(?:ing)?\\s+for\\s+(another|other)\\s+agency',
        '\\bhold(?:ing)?\\s+for\\s+agency',
        '\\bheld\\s+for\\s+(another|other)\\s+agency',
        '\\bhold(?:ing)?\\s+for\\s+[a-z].*county', '\\bhold(?:ing)?\\s+for\\s+[a-z]',
        '\\bout\\s+of\\s+county\\s+hold',
        '\\bout\\s+of\\s+county\\s+warrant', '\\bout\\s+of\\s+county\\s*/', '\\bout\\s+of\\s+county\\b',
        '\\boutside\\s+agency', '\\bagency\\s+wr(?:nt|arrant)',
        '\\bcourtesy\\s+hold', '\\bhousing\\s+for\\b',
        '\\bhold(?:ing)?\\s+for\\s+usms\\b', '\\bhold(?:ing)?\\s+for\\s+transport',
        '\\btemporary\\s+hold\\b', '\\b24\\s*hour\\s+hold', '\\bcourt\\s+order\\s+hold',
        '\\bfederal\\s+prisoner', '\\bprebook\\b',
        '\\bhold(?:ing)?\\b$', '^hold(?:ing)?\\b',
    ]),
    ('BENCH WARRANT / ALIAS WRIT', [
        '\\bbench\\s+warrant', '\\balias\\s+writ', '\\bwarrant\\b', '\\b15-10-60\\b', '\\bpublic\\s+order\\s+crimes-?aw',
        '\\balias\\b', '\\bcc\\s*-\\s*alias', '^\\s*writ\\s*$',
    ]),
    ('FAILURE TO IDENTIFY', [
        '\\bfail(ure)?\\s+to\\s+id\\b', '\\bfail(ure)?\\s+to\\s+identify', '\\bfail\\s+to\\s+id\\s+fugitive',
        '\\brefuse\\s+to\\s+give\\b',
    ]),
    ('ORGANIZED CRIMINAL ACTIVITY', [
        '\\borganized\\s+criminal\\s+activity', '\\bengaging\\s+in\\s+organized', '\\beoca\\b',
    ]),
    ('FUGITIVE FROM JUSTICE', [
        '\\bfugitive\\s+from\\s+justice', '\\bfugitive\\b',
    ]),
    ('CONTEMPT OF COURT', [
        '\\bcontempt\\b', '\\bcourt\\s+order\\b', '\\border\\s+of\\s+commitment', '\\bviolation\\s+of\\s+release\\s+order',
    ]),
    ('BAIL JUMPING / BOND VIOLATION', [
        '\\bbail\\s+jump', '\\bbond\\s+revok', '\\bviol\\s+bond', '\\b13a-10-39\\b',
    ]),
    ('PUBLIC INTOXICATION', [
        '\\bpublic\\s+intoxic', '\\bpublix\\s+intox', '\\bdrunk\\s+in\\s+public', '\\bappears\\s+in\\s+public\\s+place\\s+under\\s+influence',
        '\\balcohol\\s+intoxication\\s+in\\s+a\\s+public', '\\bintoxicated\\s+(and\\s+disruptive|persons?\\s+in\\s+public)',
        '\\bintoxicated\\s+in\\s+public', '\\bminor\\s+in\\s+possession\\s+of\\s+alcohol',
        '\\bunderage\\s+consumption', '\\bpossession\\s+of\\s+alcohol',
    ]),
    ('DISORDERLY CONDUCT', [
        '\\bdisorderly\\b', '\\bdisord(?:erly)?\\s+conduct', '\\bloitering\\b', '\\baffray\\b', '\\briot\\b',
    ]),
    ('ESCAPE / JAIL OFFENSE', [
        '\\bescape\\b', '\\bserving\\s+time', '\\bsentence\\s+to\\s+serve', '\\breturn\\s+for\\s+court',
        '\\btampering\\s+with\\s+physical\\s+evidence',
    ]),
    ('OBSTRUCTION OF JUSTICE', [
        '\\bobstruct(ing)?\\s+justice', '\\bobstruct(ing)?\\s+(an\\s+)?officer', '\\bfalse\\s+report',
        '\\bperjury\\b', '\\bfailure\\s+to\\s+obey', '\\btampering\\s+with\\s+(physical\\s+)?evidence',
    ]),
]
