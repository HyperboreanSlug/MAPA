"""Collect surname ethnicity match candidates."""
from __future__ import annotations

from typing import List, Tuple

# Filipino-list tokens that are not reliable Hispanic signals (particles,
# biblical/given names used as surnames). Spanish colonial Filipino surnames
# still map to Hispanic via filipino_hispanic_overlap.
_FILIPINO_NOT_HISPANIC_OVERLAP = frozenset({
    "de", "del", "dela", "delos", "la", "las", "los", "san", "santa", "santo",
    "david", "daniel", "gabriel", "michael", "manuel", "miguel", "pedro",
    "pablo", "juan", "maria", "jose", "jesus", "carlos", "antonio",
    "francisco", "domingo", "diego",
})


class EthnicNamesMatchMixin:
    """Build the multi-family surname match list."""

    def _surname_matches(self, surname_lc: str) -> List[Tuple[str, str]]:
        matches: List[Tuple[str, str]] = []
        indian_blocked = surname_lc in self._indian_excl_lc

        if surname_lc in self._hispanic_lc:
            matches.append(("Hispanic", "hispanic_surnames"))

        if not indian_blocked:
            if surname_lc in self._indian_hc_lc:
                matches.append(("Indian (high_confidence)", "indian_high_confidence"))
            if self.indian_surnames_by_group:
                for group, names in self._indian_group_lc.items():
                    if group == "high_confidence":
                        continue
                    if surname_lc in names:
                        matches.append((f"Indian ({group})", f"indian_{group}"))
            if surname_lc in self._indian_lc and not any(
                m[0].startswith("Indian") for m in matches
            ):
                matches.append(("Indian", "indian_surnames"))

        filipino_hit = False
        for group, names in self._asian_lc.items():
            if surname_lc in names:
                matches.append((f"Asian ({group})", f"asian_{group}"))
                if group == "filipino":
                    filipino_hit = True

        # Spanish colonial surnames dominate the Filipino list but many are
        # missing from hispanic_surnames (Gonzales, Fernandez, Alfaro, …).
        # Map them to Hispanic so White→Asian is not the label, and they still
        # surface as Hispanic surname suspects when race is White.
        if (
            filipino_hit
            and surname_lc not in self._hispanic_lc
            and surname_lc not in _FILIPINO_NOT_HISPANIC_OVERLAP
            and not any(m[0] == "Hispanic" for m in matches)
        ):
            matches.append(("Hispanic", "filipino_hispanic_overlap"))

        if surname_lc in self._african_american_lc:
            matches.append(("African American", "african_american_surnames"))

        if surname_lc in self._native_american_lc:
            matches.append(("Native American", "native_american_surnames"))

        for country, names in self._european_lc.items():
            if surname_lc in names:
                matches.append((f"European ({country})", f"european_{country}"))

        if surname_lc in self._jewish_lc:
            matches.append(("Jewish", "jewish_surnames"))

        if surname_lc in self._portuguese_lc:
            matches.append(("Portuguese", "portuguese_surnames"))

        if surname_lc in self._arabic_lc:
            matches.append(("Arabic", "arabic_surnames"))

        for region, names in self._african_lc.items():
            if surname_lc in names:
                matches.append((f"African ({region})", f"african_{region}"))

        return matches
