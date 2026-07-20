"""Surname classification for EthnicNameDatabase."""
from __future__ import annotations

from typing import List, Optional, Tuple

from scraper.ethnic_names_asian_unique import matches_are_only_asian
from scraper.ethnic_names_black_unique import is_black_only_name_combo
from scraper.ethnic_names_hispanic_unique import is_shared_hispanic_white_surname


def _is_black_family_label(ethnicity: str) -> bool:
    eth = (ethnicity or "").strip()
    return eth == "African American" or eth.startswith("African (")


class EthnicNamesClassifyMixin:
    """Surname + given-name classification and confidence."""

    def classify_by_name(
        self,
        surname: str,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
    ) -> Tuple[str, float, List[str]]:
        """
        Classify a person by surname + optional first/middle names.

        Returns (ethnicity, confidence, matching_labels).
        Confidence is intentionally conservative for multi-ethnic surnames.
        Middle names are used like first names for corroboration / dampening.

        Asian: high confidence from name alone only when the surname is
        *only Asian* (no non-Asian family hits, not a shared White/Asian name,
        not Filipino-only Spanish colonial surnames).

        Black / African: high confidence only for a *Black-only first + last*
        combo (distinctive AA given name + uniquely Black/African surname).

        Hispanic: shared White/Hispanic surnames (Martin) need a Hispanic
        given-name signal for high confidence.
        """
        if not surname:
            return ("Unknown", 0.0, [])

        self._build_lookup_sets()
        surname_lc = surname.strip().lower()
        if not surname_lc:
            return ("Unknown", 0.0, [])

        matches = self._surname_matches(surname_lc)
        if not matches:
            return ("Unknown", 0.0, [])

        fn_signal = self._resolve_given_name_signal(first_name, middle_name)
        is_amb = surname_lc in self._indian_amb_lc
        is_hc = surname_lc in self._indian_hc_lc
        is_short_surname = len(surname_lc) <= 3
        _strong_short = frozenset({
            "jha", "rao", "rai", "kaur", "nair", "jain", "bose", "modi",
            "iyer", "kaul", "goel", "saha", "das", "dev", "lal", "pal",
        })
        is_weak_with_western = is_amb or (
            is_short_surname and surname_lc not in _strong_short
        )
        has_hispanic = any(m[0] == "Hispanic" for m in matches)
        has_portuguese = any(m[0] == "Portuguese" for m in matches)
        # High Asian conf only for exclusively Asian surnames (not Lee/Park/…).
        only_asian = matches_are_only_asian(surname_lc, matches)
        # High Black conf only for AA first name + uniquely Black surname.
        # Use AA list membership (not primary signal) so dual-listed given
        # names like Jamal/Malik still qualify with uniquely Black surnames.
        aa_first = self._has_african_american_given_name(first_name, middle_name)
        black_only_combo = is_black_only_name_combo(
            surname_lc,
            has_aa_first_name=aa_first,
            matches=matches,
        )
        # Shared White/Black surnames (Washington, Mack): never high Black conf
        # from name alone — even with AA first names. Only uniquely Black
        # surname + AA first (black_only_combo) may flag White as Black.
        allow_black = black_only_combo
        if not allow_black:
            matches = [
                m for m in matches if not _is_black_family_label(m[0])
            ]
            if not matches:
                return ("Unknown", 0.0, [])

        def sort_key(item: Tuple[str, str]) -> float:
            ethnicity, _source = item
            score = 0.0
            if ethnicity == "Indian" or ethnicity.startswith("Indian ("):
                score = 1.05
                if is_amb or is_weak_with_western:
                    score = 0.55
                if is_hc and not is_amb and not is_weak_with_western:
                    score = 1.15
                if fn_signal == "indian":
                    score += 0.45
                elif fn_signal in ("anglo", "slavic"):
                    if is_amb or is_weak_with_western:
                        score -= 0.65
                    elif is_hc:
                        score -= 0.2
                    else:
                        score -= 0.35
                elif fn_signal == "hispanic":
                    score -= 0.75 if (
                        is_amb or is_weak_with_western or has_portuguese or has_hispanic
                    ) else 0.35
            elif ethnicity == "Hispanic":
                score = 0.95
                if fn_signal == "hispanic":
                    score += 0.5
                if fn_signal == "indian":
                    score -= 0.2
            elif ethnicity.startswith("Asian (filipino)"):
                # Multi-family Filipino/Hispanic names are not "only Asian".
                score = 0.9 if only_asian else 0.25
            elif ethnicity.startswith("Asian"):
                score = 1.0 if only_asian else 0.25
            elif ethnicity == "African American":
                # High conf for unique Black combo, or shared surname + AA first name.
                score = 1.45 if allow_black else 0.25
            elif ethnicity in ("Jewish", "Portuguese", "Arabic"):
                score = 0.85
                if ethnicity == "Portuguese" and fn_signal == "hispanic":
                    score += 0.35
                if ethnicity == "Portuguese" and fn_signal == "indian":
                    score += 0.15
            elif ethnicity.startswith("African ("):
                score = 1.0 if allow_black else 0.25
            elif ethnicity == "Native American":
                score = 0.55
            elif ethnicity.startswith("European"):
                score = 0.4
                if fn_signal == "anglo":
                    score += 0.25
                if fn_signal == "slavic":
                    score += 0.4
            else:
                score = 0.3
            return -score

        matches.sort(key=sort_key)
        best_match, _ = matches[0]

        forced_by_first = False
        if (
            fn_signal == "hispanic"
            and best_match.startswith("Indian")
            and (is_amb or has_portuguese or has_hispanic)
        ):
            for eth, _src in matches:
                if eth in ("Hispanic", "Portuguese"):
                    best_match = eth
                    forced_by_first = True
                    break
            else:
                best_match = "Hispanic"
                forced_by_first = True
                matches = list(matches) + [("Hispanic", "first_name_signal")]

        confidence = self._calculate_confidence(
            surname_lc,
            matches,
            best_match=best_match,
            first_name_signal=fn_signal,
            is_ambiguous=is_amb or is_weak_with_western,
            is_high_confidence_surname=is_hc and not is_weak_with_western,
        )

        if forced_by_first and best_match in ("Hispanic", "Portuguese"):
            confidence = min(confidence, 0.62)
            confidence = max(confidence, 0.52)

        if best_match.startswith("Indian") and (is_amb or is_weak_with_western):
            if fn_signal in ("anglo", "slavic"):
                confidence = min(confidence, 0.32)
            elif fn_signal == "hispanic":
                confidence = min(confidence, 0.25)
            elif fn_signal == "unknown":
                confidence = min(confidence, 0.42)
        elif best_match.startswith("Indian") and fn_signal in ("anglo", "slavic") and is_hc:
            confidence = min(confidence, 0.55)

        # Name alone must not flag White as Asian unless surname is only Asian.
        if best_match.startswith("Asian") and not only_asian:
            confidence = min(confidence, 0.35)

        # Name alone must not flag White as Black unless allowed Black combo.
        if _is_black_family_label(best_match) and not allow_black:
            confidence = min(confidence, 0.35)

        # Shared White/Hispanic (Martin): need Hispanic given name for high conf.
        if (
            best_match == "Hispanic"
            and is_shared_hispanic_white_surname(surname_lc)
            and fn_signal != "hispanic"
        ):
            confidence = min(confidence, 0.35)

        return (best_match, confidence, [m[0] for m in matches])