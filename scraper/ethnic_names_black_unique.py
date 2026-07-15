"""Only-*Black* first+last name rules for misclassification detection.

Common English/American surnames (Washington, Banks, Jefferson, …) appear in
both White and Black populations. Distinctive African-American given names
(DeShawn, Jamal, …) alone are not enough either.

Name analysis may mark race=White as Black only when *both* are Black-only:
  * first name is a distinctive African-American given-name signal, and
  * surname is uniquely Black / African (not a shared White/Black surname),
    and matches at least one African American or African list.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

# English/Irish/French surnames that collide with real African ethnics or are
# too short / multi-ethnic to treat as uniquely Black.
_AFRICAN_ENGLISH_COLLISIONS = frozenset({
    "wade",   # English; also Wolof — not unique
    "fall",   # English; also Wolof
    "kane",   # Irish; also Wolof
    "barry",  # Irish/English; also listed AA
    "ba",     # too short / multi-use
    "sy",     # too short
    "jean", "michel", "noel",  # Francophone shared
    "lee", "king", "brown", "smith", "jones", "williams",
})

# Common US English/American surnames that also appear on AA lists.
# Shared Black/White heritage — not uniquely Black.
_COMMON_US_ENGLISH_SURNAMES = frozenset({
    "adams", "alexander", "allen", "anderson", "bailey", "baker", "banks",
    "barnes", "bell", "bennett", "boyd", "brooks", "brown", "bryant",
    "butler", "campbell", "carter", "charles", "clark", "cole", "coleman",
    "collins", "cook", "cooper", "cotton", "cox", "davis", "diggs",
    "dorsey", "dunbar", "edwards", "ellis", "ellison", "epps", "evans",
    "fisher", "ford", "foster", "freeman", "gibson", "graham", "gray",
    "green", "griffin", "hall", "hamilton", "harris", "harrison", "hayes",
    "henderson", "hill", "howard", "hughes", "jackson", "james", "jefferson",
    "jenkins", "johnson", "jones", "jordan", "kelly", "kennedy", "king",
    "lee", "lewis", "long", "marshall", "martin", "mason", "miller",
    "mitchell", "montgomery", "moore", "morgan", "morris", "murphy",
    "murray", "myers", "nelson", "owens", "parker", "patterson", "perry",
    "peterson", "phillips", "powell", "price", "reed", "reynolds",
    "richardson", "roberts", "robinson", "rogers", "ross", "russell",
    "sanders", "scott", "simmons", "simpson", "smith", "stevens",
    "stewart", "sullivan", "taylor", "thomas", "thompson", "turner",
    "walker", "wallace", "ward", "washington", "watson", "webb", "wells",
    "west", "white", "williams", "wilson", "wood", "woods", "wright",
    "young", "ashford", "bolden", "bonner", "booker", "burrell", "cowans",
    "crump", "dabney", "dozier", "dupree",
})


def is_shared_black_white_surname(surname: Optional[str]) -> bool:
    """True when the surname is common to White and Black populations."""
    s = (surname or "").strip().lower()
    if not s:
        return False
    if s in _AFRICAN_ENGLISH_COLLISIONS:
        return True
    if s in _COMMON_US_ENGLISH_SURNAMES:
        return True
    return False


def is_uniquely_black_surname(surname: Optional[str]) -> bool:
    """Inverse of shared — caller still checks list membership."""
    return not is_shared_black_white_surname(surname)


def _has_black_family_match(matches: Iterable[Tuple[str, str]]) -> bool:
    for ethnicity, _source in matches:
        eth = (ethnicity or "").strip()
        if eth == "African American" or eth.startswith("African ("):
            return True
    return False


def is_black_only_name_combo(
    surname: Optional[str],
    *,
    has_aa_first_name: bool,
    matches: Iterable[Tuple[str, str]],
) -> bool:
    """True only for Black-only first name + uniquely Black surname.

    Used to allow high-confidence Black / African labels from name analysis.

    *has_aa_first_name* should be True when any given-name token is on the
    African-American first-name list (checked directly so dual-listed names
    like Jamal/Malik still count even if the primary signal prefers Indian).
    """
    if not has_aa_first_name:
        return False
    if not is_uniquely_black_surname(surname):
        return False
    return _has_black_family_match(matches)
