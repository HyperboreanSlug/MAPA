"""Ethnic name database for misclassification detection.

Methodology (important):
  * Surname alone is NEVER enough for high confidence on ambiguous names
    (e.g. Gill, Perera, Silva) that appear across multiple ethnic groups.
  * First names are scored together with surnames. Anglo first names
    (Amy, John, …) tank confidence for weak/ambiguous Indian surnames.
  * Hispanic first names (Alberto, Carlos, …) with Luso/Hispanic-overlapping
    surnames (Perera, Silva, …) prefer Hispanic / low Indian confidence.
  * Distinctive high-confidence Indian surnames (Patel, Singh, …) stay strong
    unless the first name strongly contradicts.
"""
from __future__ import annotations


from typing import List, Tuple


class EthnicNamesConfidenceMixin:
    """Confidence scoring and simple surname membership queries."""

    def get_likely_ethnicity(
        self,
        surname: str,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
    ) -> Tuple[str, float]:
        """Get the most likely ethnicity for a name."""
        ethnicity, confidence, _ = self.classify_by_name(
            surname, first_name=first_name, middle_name=middle_name
        )
        return (ethnicity, confidence)

    def is_hispanic_surname(self, surname: str) -> bool:
        self._build_lookup_sets()
        return surname.strip().lower() in self._hispanic_lc

    def is_asian_surname(self, surname: str) -> Tuple[bool, str]:
        self._build_lookup_sets()
        surname_lc = surname.strip().lower()
        for group, names in self._asian_lc.items():
            if surname_lc in names:
                return True, group
        return False, ""

    def is_indian_surname(self, surname: str) -> bool:
        self._build_lookup_sets()
        lc = surname.strip().lower()
        if lc in self._indian_excl_lc:
            return False
        return lc in self._indian_lc

    def is_indian_high_confidence_surname(self, surname: str) -> bool:
        self._build_lookup_sets()
        lc = surname.strip().lower()
        if lc in self._indian_excl_lc:
            return False
        return lc in self._indian_hc_lc

    def is_indian_ambiguous_surname(self, surname: str) -> bool:
        self._build_lookup_sets()
        return surname.strip().lower() in self._indian_amb_lc

    def subcategories(self, ethnicity: str) -> List[str]:
        eth = (ethnicity or "").lower().strip()
        if eth in (
            "indian_high_confidence",
            "high_confidence_indian",
            "high-confidence indian",
            "indian_hc",
        ):
            return ["all"]
        if eth == "asian":
            return ["all"] + sorted(self.asian_surnames.keys(), key=str.lower)
        if eth == "indian":
            groups = sorted((self.indian_surnames_by_group or {}).keys(), key=str.lower)
            if "high_confidence" in groups:
                groups = ["high_confidence"] + [g for g in groups if g != "high_confidence"]
            return ["all"] + groups if groups else ["all"]
        if eth == "european":
            return ["all"] + sorted(self.european_surnames.keys(), key=str.lower)
        if eth == "african":
            return ["all"] + sorted(self.african_surnames.keys(), key=str.lower)
        return ["all"]

    def has_subcategories(self, ethnicity: str) -> bool:
        return len(self.subcategories(ethnicity)) > 1

    def is_african_american_surname(self, surname: str) -> bool:
        self._build_lookup_sets()
        return surname.strip().lower() in self._african_american_lc

    def _calculate_confidence(
        self,
        surname: str,
        matches: List[Tuple[str, str]],
        *,
        best_match: str,
        first_name_signal: str,
        is_ambiguous: bool,
        is_high_confidence_surname: bool,
    ) -> float:
        """Confidence from surname specificity + first-name corroboration."""
        if not matches:
            return 0.0

        sources = {src for _eth, src in matches}
        multi_family = self._family_count(matches) > 1

        # Base from surname quality
        if best_match.startswith("Indian"):
            if is_high_confidence_surname and not is_ambiguous:
                base = 0.92 if not multi_family else 0.85
            elif is_ambiguous:
                # Surname alone is weak evidence
                base = 0.38
            else:
                base = 0.72 if not multi_family else 0.58
        elif best_match == "Hispanic":
            base = 0.85 if not multi_family else 0.7
        elif best_match.startswith("Asian"):
            base = 0.85 if not multi_family else 0.7
        elif best_match == "African American":
            base = 0.85 if not multi_family else 0.7
        else:
            base = 0.8 if len(matches) == 1 else 0.65

        # First-name adjustment
        if best_match == "African American" or best_match.startswith("African ("):
            if first_name_signal == "african_american":
                base = min(1.0, base + 0.12)  # DeShawn + unique Black surname
            elif first_name_signal in ("anglo", "slavic"):
                base = min(base, 0.45)  # John Washington / John Mwangi
            elif first_name_signal == "hispanic":
                base = min(base, 0.5)
            # Dual-listed given names (Jamal/Malik) may signal "indian" while
            # still being on the AA first-name list — do not dampen Black here;
            # the black-only combo gate in classify handles allow/deny.
        elif first_name_signal == "indian":
            if best_match.startswith("Indian"):
                base = min(1.0, base + (0.4 if is_ambiguous else 0.12))
            elif best_match in ("Hispanic", "Portuguese"):
                base = max(0.35, base - 0.15)
        elif first_name_signal == "hispanic":
            if best_match.startswith("Indian"):
                base = min(base, 0.25 if is_ambiguous else 0.4)
            elif best_match in ("Hispanic", "Portuguese"):
                base = min(1.0, base + 0.12)
        elif first_name_signal in ("anglo", "slavic"):
            # Andrey ≈ white Western; Andrei ≈ Slavic — neither supports Indian
            if best_match.startswith("Indian"):
                if is_ambiguous:
                    base = min(base, 0.28)
                elif is_high_confidence_surname:
                    base = min(base, 0.55)
                else:
                    base = min(base, 0.45)
            elif best_match.startswith("European"):
                base = min(1.0, base + (0.15 if first_name_signal == "slavic" else 0.1))

        if multi_family and not best_match.startswith("Indian"):
            base -= 0.08 * (self._family_count(matches) - 1)

        if "indian_high_confidence" in sources and best_match.startswith("Indian"):
            if first_name_signal == "indian":
                base = max(base, 0.9)

        return round(max(0.15, min(base, 1.0)), 2)

    @staticmethod
    def _family_count(matches: List[Tuple[str, str]]) -> int:
        families = set()
        for ethnicity, _source in matches:
            if ethnicity == "Indian" or ethnicity.startswith("Indian ("):
                families.add("indian")
            elif ethnicity.startswith("Asian"):
                families.add("asian")
            elif ethnicity.startswith("European"):
                families.add("european")
            elif ethnicity.startswith("African ("):
                families.add("african")
            else:
                families.add(ethnicity.lower())
        return len(families)

