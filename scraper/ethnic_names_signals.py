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


import re
import unicodedata
from typing import List, Optional


class EthnicNamesSignalsMixin:
    """Given-name signals and accent folding."""

    def _build_lookup_sets(self) -> None:
        """Cache lowercased sets for O(1) membership checks."""
        if getattr(self, "_lookups_ready", False):
            return
        self._hispanic_lc = {n.lower() for n in self.hispanic_surnames}
        self._african_american_lc = {n.lower() for n in self.african_american_surnames}
        self._native_american_lc = {n.lower() for n in self.native_american_surnames}
        self._jewish_lc = {n.lower() for n in self.jewish_surnames}
        self._portuguese_lc = {n.lower() for n in self.portuguese_surnames}
        self._arabic_lc = {n.lower() for n in self.arabic_surnames}
        self._indian_excl_lc = {
            n.lower() for n in (self.indian_surname_exclusions or set())
        }
        self._indian_amb_lc = {
            n.lower() for n in (self.indian_ambiguous_surnames or set())
        }
        self._indian_lc = {
            n.lower() for n in self.indian_surnames
            if n.lower() not in self._indian_excl_lc
        }
        self._indian_hc_lc = {
            n.lower() for n in (self.indian_high_confidence_surnames or set())
            if n.lower() not in self._indian_excl_lc
        }
        self._indian_group_lc = {
            group: {
                n.lower() for n in names if n.lower() not in self._indian_excl_lc
            }
            for group, names in (self.indian_surnames_by_group or {}).items()
        }
        def _fold_set(names) -> set:
            out = set()
            for n in names or set():
                out.add(self._fold_accents(str(n)).lower())
            return out

        self._indian_first_lc = _fold_set(self.indian_first_names)
        self._hispanic_first_lc = _fold_set(self.hispanic_first_names)
        self._anglo_first_lc = _fold_set(self.anglo_western_first_names)
        self._slavic_first_lc = _fold_set(self.slavic_first_names)
        self._aa_first_lc = _fold_set(self.african_american_first_names)
        self._asian_lc = {
            group: {n.lower() for n in names}
            for group, names in self.asian_surnames.items()
        }
        self._european_lc = {
            country: {n.lower() for n in names}
            for country, names in self.european_surnames.items()
        }
        self._african_lc = {
            region: {n.lower() for n in names}
            for region, names in self.african_surnames.items()
        }
        self._lookups_ready = True


    @staticmethod
    def _fold_accents(text: str) -> str:
        """CRISTÓBAL → cristobal for list matching."""
        if not text:
            return ""
        nfkd = unicodedata.normalize("NFKD", text)
        return "".join(c for c in nfkd if not unicodedata.combining(c))

    @classmethod
    def _normalize_given_name(cls, first_name: Optional[str]) -> str:
        """First token of given name, letters only (handles 'MARY-ANN', 'J.')."""
        if not first_name:
            return ""
        raw = str(first_name).strip()
        if not raw:
            return ""
        # Take first whitespace token; strip punctuation
        token = raw.replace(",", " ").split()[0]
        token = re.sub(r"[^A-Za-zÀ-ÖØ-öø-ÿ\-']", "", token)
        token = token.strip("-'")
        return cls._fold_accents(token).lower()

    def _first_name_signal(self, first_name: Optional[str]) -> str:
        """
        Return one of: indian | african_american | hispanic | anglo | slavic | unknown

        Note: *Andrey* is treated as Western/white; *Andrei* as Slavic.
        Neither boosts Indian surname confidence.
        """
        self._build_lookup_sets()
        fn = self._normalize_given_name(first_name)
        if not fn or len(fn) < 2:
            return "unknown"
        # Prefer more specific lists; allow dual membership to favor indian
        # only when explicitly in indian list
        if fn in self._indian_first_lc:
            return "indian"
        # Distinctive African-American given names (DeShawn, Jamal, Lakisha…)
        if fn in self._aa_first_lc:
            return "african_american"
        # Slavic before Hispanic so Ivan/Andrei stay Slavic (not Spanish-default)
        if fn in self._slavic_first_lc:
            return "slavic"
        if fn in self._hispanic_first_lc:
            return "hispanic"
        if fn in self._anglo_first_lc:
            return "anglo"
        return "unknown"

    @staticmethod
    def _is_western_first_signal(signal: str) -> bool:
        """First names that contradict South Asian ethnicity claims."""
        return signal in ("anglo", "slavic", "hispanic")

    def _iter_given_name_tokens(
        self,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
    ) -> List[str]:
        """Normalized given-name tokens from first + middle (skip initials)."""
        tokens: List[str] = []
        for part in (first_name, middle_name):
            if not part:
                continue
            for tok in re.split(r"[\s\-]+", str(part).strip()):
                if not tok or len(tok) < 2:
                    continue
                if len(tok) == 2 and tok.endswith("."):
                    continue
                norm = self._normalize_given_name(tok)
                if norm and len(norm) >= 2:
                    tokens.append(norm)
        return tokens

    def _has_african_american_given_name(
        self,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
    ) -> bool:
        """True if any given-name token is on the AA first-name list."""
        self._build_lookup_sets()
        for tok in self._iter_given_name_tokens(first_name, middle_name):
            if tok in self._aa_first_lc:
                return True
        return False

    def _resolve_given_name_signal(
        self,
        first_name: Optional[str] = None,
        middle_name: Optional[str] = None,
    ) -> str:
        """
        Combine first + middle name signals for ethnicity confidence.

        Any Indic given name (first or middle) corroborates Indian surnames.
        Western / Slavic / Hispanic signals dampen when no Indic given name.
        """
        signals: List[str] = []
        for part in (first_name, middle_name):
            if not part:
                continue
            # Score each token in multi-word middle names (e.g. "ZAHEER UDDIN")
            tokens = re.split(r"[\s\-]+", str(part).strip())
            for tok in tokens:
                if not tok or len(tok) < 2:
                    continue
                # Skip bare initials
                if len(tok) == 1 or (len(tok) == 2 and tok.endswith(".")):
                    continue
                sig = self._first_name_signal(tok)
                if sig != "unknown":
                    signals.append(sig)
        if not signals:
            return "unknown"
        if "indian" in signals:
            return "indian"
        if "african_american" in signals:
            return "african_american"
        if "slavic" in signals:
            return "slavic"
        if "hispanic" in signals:
            return "hispanic"
        if "anglo" in signals:
            return "anglo"
        return "unknown"

