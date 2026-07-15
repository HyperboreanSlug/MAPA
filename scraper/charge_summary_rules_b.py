"""Charge summary patterns (_SUMMARY_RULES_B)."""
from __future__ import annotations

from typing import List, Tuple

_SUMMARY_RULES_B: List[Tuple[str, List[str]]] = [
    ('ROBBERY', [
        '\\brobbery\\b', '\\bcarjack', '\\bstrong.?arm',
    ]),
    ('ASSAULT / BATTERY', [
        '\\baggravated\\s+assault', '\\bfelonious\\s+assault', '\\bsimple\\s+assault',
        '\\bassault\\b', '\\bbatter(?:y|ing)\\b', '\\bstrangul', '\\bterroristic\\s+threat', '\\bthreat\\s+to\\s+(kill|injure)',
        '\\bmalicious\\s+wound', '\\bmayhem\\b', '\\bmenacing\\b', '\\bcommunicating\\s+threats',
        '\\breckless\\s+endanger', '\\bbodily\\s+harm',
    ]),
    ('KIDNAPPING / FALSE IMPRISONMENT', [
        '\\bkidnap', '\\bfalse\\s+imprison', '\\bunlawful\\s+restraint', '\\bunl\\s+restraint',
        '\\bcriminal\\s+restraint',
    ]),
    ('STALKING / HARASSMENT', [
        '\\bstalking\\b', '\\bharass', '\\bintimidation\\b', '\\bharassing\\s+communications',
    ]),
    ('RESISTING ARREST', [
        '\\bresist(ing)?\\s+(arrest|officer|public\\s+officer)', '\\bresist(ing)?\\s+officer\\s+without\\s+violence',
        '\\bresist(ing)?\\s+(law\\s+enforcement|public\\s+officer)', '\\bobstruct(ing)?\\s+(officer|police|governmental)',
    ]),
    ('DRUG TRAFFICKING', [
        '\\bdrug\\s+traffick', '\\btraffick.*drug', '\\bintent\\s+to\\s+(distrib|deliver|sell)',
        '\\bdelivery\\s+of\\b', '\\bpwid\\b', '\\bmanufacture.*controlled', '\\bman\\s*del\\s+cs\\b',
    ]),
    ('POSSESSION OF MARIJUANA', [
        '\\bposs(ession)?\\s+of\\s+marij', '\\bmarijuana\\b', '\\bcannabis\\b', '\\bpom\\b',
        '\\bupom\\b', '\\b13a-12-213\\b',
    ]),
    ('POSSESSION OF METHAMPHETAMINE', [
        '\\bmeth(amphetamine)?\\b', '\\bmethamphetamine-?possess',
    ]),
    ('DRUG PARAPHERNALIA', [
        '\\bparaphernalia\\b', '\\bparaphernilia\\b', '\\buse/possession\\s+drug\\s+paraphernalia',
        '\\bupodp\\b', '\\b13a-12-260\\b',
    ]),
    ('POSSESSION OF CONTROLLED SUBSTANCE', [
        '\\bcontroll?ed\\s+substance', '\\bpossession\\s+of\\s+controlled', '\\bunlawful\\s+possession\\s+controlled',
        '\\bposs(ession)?\\s+of\\s+dangerous\\s+drugs', '\\bpossession\\s+of\\s+a\\s+controlled',
        '\\bposs\\s+cs\\b', '\\bupocs\\b', '\\bposs(ess|ession)?/?receive\\s+cont', '\\bcocaine\\b',
        '\\bheroin\\b', '\\bfentanyl\\b', '\\bnarcotic', '\\bcds\\b', '\\b13a-12-212\\b',
        '\\bdangerous\\s+drugs\\b',
    ]),
    ('BURGLARY / B&E', [
        '\\bburglar', '\\bb\\s*&\\s*e\\b', '\\bbreaking\\s+and\\s+enter', '\\bhome\\s+invasion',
        '\\bunlawful\\s+entry',
    ]),
    ('THEFT / LARCENY', [
        '\\btheft\\s+of\\s+property', '\\bgrand\\s+theft', '\\bpetit\\s+theft', '\\bpetty\\s+theft',
        '\\btheft\\b', '\\blarceny\\b', '\\bshoplift', '\\bstolen\\s+propert', '\\breceiv(ing|ed)\\s+stolen',
        '\\bmotor\\s+vehicle\\s+theft', '\\bauto\\s+theft', '\\bunlawful\\s+taking',
        '\\bcriminal\\s+damage\\s+to\\s+property',
    ]),
    ('WEAPONS OFFENSE', [
        '\\bfirearm', '\\bhandgun\\b', '\\brifle\\b', '\\bshotgun\\b', '\\bweapon', '\\bconcealed\\s+carry',
        '\\bammunition\\b', '\\bbrandish', '\\bdeadly\\s+weapon', '\\bexplosive', '\\buuw\\b',
    ]),
    ('CRIMINAL TRESPASS', [
        '\\btrespass', '\\bcriminal\\s+trespass',
    ]),
]
