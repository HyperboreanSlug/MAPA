"""Search arrest records and detect ethnic surname vs race misclassifications.

Primary product purpose: flag potential race/ethnicity misclassifications
when a published arrest record's surname strongly suggests one ethnicity
but the recorded race field is incompatible.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .database import Database
from .ethnic_names import EthnicNameDatabase


@dataclass
class SearchResults:
    records: List[Dict[str, Any]]
    total_count: int
    query_time_ms: float
    filters_applied: Dict[str, str] = field(default_factory=dict)


@dataclass
class Misclassification:
    record: Dict[str, Any]
    expected_race: str  # recorded race on the arrest row
    likely_ethnicity: str  # from surname
    confidence: float
    matching_names: List[str] = field(default_factory=list)


_ETHNICITY_COMPATIBLE_RACES = {
    "hispanic": {"HISPANIC", "LATINO", "LATINA", "LATINX", "H", "WHITE HISPANIC"},
    "asian": {
        "ASIAN", "ASIAN / PACIFIC ISLANDER", "ASIAN/PACIFIC ISLANDER",
        "PACIFIC ISLANDER", "A", "API", "CHINESE", "KOREAN", "JAPANESE",
        "VIETNAMESE", "FILIPINO", "OTHER ASIAN",
    },
    "indian": {
        "ASIAN", "ASIAN / PACIFIC ISLANDER", "ASIAN/PACIFIC ISLANDER",
        "ASIAN INDIAN", "EAST INDIAN", "INDIAN", "SOUTH ASIAN",
        "A", "API", "OTHER", "OTHER ASIAN", "UNKNOWN", "U",
    },
    "african_american": {
        "BLACK", "AFRICAN AMERICAN", "AFRICAN-AMERICAN", "B",
        "BLACK OR AFRICAN AMERICAN",
    },
    "native_american": {
        "NATIVE AMERICAN", "AMERICAN INDIAN",
        "AMERICAN INDIAN OR ALASKA NATIVE", "ALASKA NATIVE", "I", "NATIVE",
    },
    "arabic": {"WHITE", "OTHER", "MIDDLE EASTERN", "ARAB", "W"},
    "jewish": {"WHITE", "OTHER", "W"},
    "portuguese": {"WHITE", "HISPANIC", "OTHER", "W"},
    "european": {"WHITE", "CAUCASIAN", "W"},
    "african": {
        "BLACK", "AFRICAN AMERICAN", "AFRICAN-AMERICAN", "B",
        "BLACK OR AFRICAN AMERICAN",
    },
}

_RACE_ALIASES = {
    "W": "WHITE", "CAUCASIAN": "WHITE", "CAUCASION": "WHITE", "WHITE": "WHITE",
    "B": "BLACK", "BLACK": "BLACK", "AFRICAN AMERICAN": "BLACK",
    "AFRICAN-AMERICAN": "BLACK", "BLACK OR AFRICAN AMERICAN": "BLACK",
    "H": "HISPANIC", "LATINO": "HISPANIC", "LATINA": "HISPANIC",
    "LATINX": "HISPANIC", "HISPANIC": "HISPANIC",
    "A": "ASIAN", "API": "ASIAN", "ASIAN": "ASIAN",
    "U": "UNKNOWN", "UNK": "UNKNOWN", "UNKNOWN": "UNKNOWN",
    "N/A": "UNKNOWN", "NA": "UNKNOWN", "NONE": "UNKNOWN", "NULL": "UNKNOWN",
    "": "UNKNOWN",
    # LAPD descent codes often used in open data
    "C": "WHITE",  # sometimes Chinese in LAPD — ambiguous; leave as C if needed
    "F": "ASIAN",  # Filipino
    "K": "ASIAN",  # Korean
    "J": "ASIAN",  # Japanese
    "V": "ASIAN",  # Vietnamese
    "Z": "ASIAN",  # Asian Indian in some LAPD coding
    "P": "PACIFIC ISLANDER",
    "I": "NATIVE AMERICAN",
    "O": "OTHER",
    "X": "UNKNOWN",
    "G": "OTHER",  # Guamanian etc. varies
}


def _canonical_race_key(recorded_race: str) -> str:
    raw = (recorded_race or "").strip()
    if not raw or raw.upper() in ("N/A", "NA"):
        return "UNKNOWN"
    r = " ".join(raw.upper().replace("_", " ").replace("-", " ").split())
    r = r.replace(" / ", "/").replace("/ ", "/").replace(" /", "/")
    r_spaced = " ".join(r.replace("/", " ").split())
    if r_spaced in _RACE_ALIASES:
        return _RACE_ALIASES[r_spaced]
    if len(r_spaced) == 1 and r_spaced in _RACE_ALIASES:
        return _RACE_ALIASES[r_spaced]
    if r_spaced in ("OTHER ASIAN", "ASIAN OTHER"):
        return "OTHER ASIAN"
    if "OTHER" in r_spaced and "ASIAN" in r_spaced:
        return "OTHER ASIAN"
    if "HISPANIC" in r_spaced and "WHITE" in r_spaced:
        return "WHITE HISPANIC"
    if r_spaced.startswith("WHITE") or r_spaced.endswith(" WHITE"):
        return "WHITE"
    if r_spaced in ("OTHER", "OTHER RACE", "OTHER RACES", "OT"):
        return "OTHER"
    if "ASIAN" in r_spaced and "PACIFIC" in r_spaced:
        return "ASIAN / PACIFIC ISLANDER"
    return r_spaced


def format_race_label(recorded_race: str) -> str:
    key = _canonical_race_key(recorded_race)
    if key == "UNKNOWN":
        raw = (recorded_race or "").strip()
        return raw if raw else "—"
    if len(key) <= 2:
        return key
    return key.title().replace("Or", "or").replace("/ ", "/")


def _ethnicity_family(likely_ethnicity: str) -> str:
    eth = (likely_ethnicity or "").strip().lower()
    if eth == "indian" or eth.startswith("indian") or "high_confidence" in eth:
        return "indian"
    if eth.startswith("asian"):
        return "asian"
    if eth.startswith("european"):
        return "european"
    if eth.startswith("african (") or eth == "african":
        return "african"
    if eth in ("african american", "african-american"):
        return "african_american"
    if eth in ("native american", "native-american"):
        return "native_american"
    if eth == "hispanic":
        return "hispanic"
    if eth == "jewish":
        return "jewish"
    if eth == "portuguese":
        return "portuguese"
    if eth == "arabic":
        return "arabic"
    return eth.replace(" ", "_")


def _is_other_or_other_asian(race_key: str) -> bool:
    r = (race_key or "").strip().upper()
    if r in ("OTHER", "OTHER ASIAN", "UNKNOWN"):
        return True
    if "OTHER" in r and "ASIAN" in r:
        return True
    return False


def _is_compatible(likely_ethnicity: str, recorded_race: str) -> bool:
    if not recorded_race or not likely_ethnicity or likely_ethnicity == "Unknown":
        return True
    family = _ethnicity_family(likely_ethnicity)
    race = _canonical_race_key(recorded_race)
    if family == "indian" and _is_other_or_other_asian(race):
        return True
    compatible = _ETHNICITY_COMPATIBLE_RACES.get(family)
    if not compatible:
        return race == likely_ethnicity.strip().upper()
    if race in compatible:
        return True
    raw_u = " ".join((recorded_race or "").strip().upper().split())
    return raw_u in compatible


def _last_name_from_record(record: Dict[str, Any]) -> str:
    last = (record.get("last_name") or record.get("LastName") or "").strip()
    if last:
        return last
    full = (record.get("full_name") or record.get("Name") or "").strip()
    if full:
        parts = full.replace(",", " ").split()
        if parts:
            return parts[-1]
    return ""


def _first_name_from_record(record: Dict[str, Any]) -> str:
    """Given name only (no middle) — used with SOR-parity first-name confidence."""
    first = (record.get("first_name") or record.get("FirstName") or "").strip()
    if first:
        return first.split()[0]
    full = (record.get("full_name") or record.get("Name") or "").strip()
    if full:
        parts = full.replace(",", " ").split()
        if len(parts) >= 2:
            return parts[0]
    return ""


class ArrestSearcher:
    """Search arrests and run ethnic misclassification analysis (primary purpose)."""

    def __init__(self, db_path: Optional[str] = None):
        self.db = Database(db_path)
        self.ethnic_db = EthnicNameDatabase()

    def search_by_name(
        self,
        name: str,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> SearchResults:
        start = time.time()
        records = self.db.search_by_name(
            name,
            state=state,
            race=race,
            charge_category=charge_category,
            limit=limit,
            offset=offset,
        )
        return SearchResults(
            records=records,
            total_count=len(records),
            query_time_ms=(time.time() - start) * 1000,
            filters_applied={
                "name": name,
                "state": state or "",
                "race": race or "",
                "charge_category": charge_category or "",
            },
        )

    def search(
        self,
        *,
        name: Optional[str] = None,
        state: Optional[str] = None,
        race: Optional[str] = None,
        charge_category: Optional[str] = None,
        limit: int = 1000,
    ) -> SearchResults:
        start = time.time()
        records = self.db.search_records(
            name=name,
            state=state,
            race=race,
            charge_category=charge_category,
            limit=limit,
        )
        return SearchResults(
            records=records,
            total_count=len(records),
            query_time_ms=(time.time() - start) * 1000,
            filters_applied={
                "name": name or "",
                "state": state or "",
                "race": race or "",
                "charge_category": charge_category or "",
            },
        )

    def analyze_ethnicities(
        self,
        min_confidence: float = 0.5,
        limit: int = 0,
        ethnicity_filter: Optional[str] = None,
        charge_category: Optional[str] = None,
        return_base_count: bool = False,
        named_only: bool = True,
    ):
        """
        Primary analysis: surname ethnicity vs recorded race on arrest rows.

        Only rows with a last/full name can be classified. Open-data sources
        without names never appear here (by design when named_only=True).
        Optional charge_category narrows to e.g. sex_crimes or burglary_be.
        """
        from .charge_classifications import classify_charge

        misclassifications: List[Misclassification] = []
        base_count = 0
        filter_key = (ethnicity_filter or "").strip().lower() or None
        charge_f = (charge_category or "").strip().lower() or None
        if charge_f in ("all", "*", ""):
            charge_f = None
        hc_only = filter_key in (
            "indian_high_confidence",
            "high_confidence_indian",
            "high-confidence indian",
            "indian_hc",
        )
        family_filter = "indian" if hc_only else filter_key
        scan_limit = None if limit is None or int(limit) <= 0 else int(limit)
        newest_first = bool(scan_limit)

        for record in self.db.iter_arrests(
            limit=scan_limit,
            newest_first=newest_first,
            named_only=named_only,
            charge_category=charge_f,
        ):
            # Fallback classify if column empty (legacy rows)
            if charge_f:
                cat = (record.get("charge_category") or "").strip().lower()
                if not cat or cat == "unknown":
                    cat = classify_charge(record)
                    record["charge_category"] = cat
                if cat != charge_f:
                    continue
            last_name = _last_name_from_record(record)
            first_name = _first_name_from_record(record)
            recorded_race = (record.get("race") or "").strip()
            if not last_name:
                continue
            if hc_only and not self.ethnic_db.is_indian_high_confidence_surname(last_name):
                continue
            # Parity with SOR: first-name scoring + ambiguous surname floors
            likely_eth, confidence, matching_names = self.ethnic_db.classify_by_name(
                last_name, first_name=first_name or None
            )
            if confidence < min_confidence or likely_eth == "Unknown":
                continue
            family = _ethnicity_family(likely_eth)
            if family_filter and family != family_filter:
                continue
            base_count += 1
            if _is_compatible(likely_eth, recorded_race):
                continue
            if not record.get("charge_category"):
                record["charge_category"] = classify_charge(record)
            # Persist analysis fields on the in-memory row for export/UI
            record["likely_ethnicity"] = likely_eth
            record["name_confidence"] = confidence
            misclassifications.append(
                Misclassification(
                    record=record,
                    expected_race=format_race_label(recorded_race)
                    if recorded_race
                    else "—",
                    likely_ethnicity=likely_eth,
                    confidence=confidence,
                    matching_names=matching_names,
                )
            )

        misclassifications.sort(key=lambda m: m.confidence, reverse=True)
        if return_base_count:
            return misclassifications, base_count
        return misclassifications

    def get_total_count(self) -> int:
        return self.db.get_total_count()

    def get_race_distribution(self):
        return self.db.get_race_distribution()

    def get_state_distribution(self):
        return self.db.get_state_distribution()

    def export_misclassifications(
        self,
        output_path: str,
        ethnicity_filter: Optional[str] = None,
        charge_category: Optional[str] = None,
        min_confidence: float = 0.5,
        limit: int = 0,
    ) -> int:
        import csv

        from .charge_classifications import category_label

        results = self.analyze_ethnicities(
            min_confidence=min_confidence,
            limit=limit,
            ethnicity_filter=ethnicity_filter,
            charge_category=charge_category,
        )
        if not results:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    [
                        "name", "recorded_race", "likely_ethnicity", "confidence",
                        "charge", "charge_category", "state", "arrest_date",
                        "source_system",
                    ]
                )
            return 0
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(
                f,
                fieldnames=[
                    "name", "recorded_race", "likely_ethnicity", "confidence",
                    "charge", "charge_category", "state", "arrest_date",
                    "source_system", "source_url",
                ],
            )
            w.writeheader()
            for mc in results:
                rec = mc.record or {}
                name = (
                    f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
                ).strip() or (rec.get("full_name") or "")
                cat = rec.get("charge_category") or ""
                w.writerow({
                    "name": name,
                    "recorded_race": mc.expected_race,
                    "likely_ethnicity": mc.likely_ethnicity,
                    "confidence": f"{mc.confidence:.3f}",
                    "charge": rec.get("charge_description") or "",
                    "charge_category": category_label(cat) if cat else "",
                    "state": rec.get("state") or "",
                    "arrest_date": rec.get("arrest_date") or rec.get("booking_date") or "",
                    "source_system": rec.get("source_system") or "",
                    "source_url": rec.get("source_url") or "",
                })
        return len(results)

    def get_charge_category_distribution(self):
        return self.db.get_charge_category_distribution()

    def close(self) -> None:
        self.db.close()


# Back-compat alias used by package __init__
SexOffenderSearcher = ArrestSearcher

_searcher: Optional[ArrestSearcher] = None


def get_searcher(db_path: Optional[str] = None) -> ArrestSearcher:
    global _searcher
    if db_path is not None:
        return ArrestSearcher(db_path)
    if _searcher is None:
        _searcher = ArrestSearcher()
    return _searcher
