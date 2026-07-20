"""Filter browse rows to surname-vs-stated-race misclassification suspects."""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_ACTUAL_RACES,
    actual_race_filter_values,
)
from scraper.identity_review import (
    dedupe_records_by_person,
    is_person_reviewed,
)
from scraper.searcher import ethnicity_review_verdict


def resolve_actual_filter(actual: Optional[str]) -> Tuple[Optional[str], Optional[List[str]]]:
    """Map UI actual-race filter → search kwargs (single value or IN-list)."""
    if actual in BROWSE_ACTUAL_RACES:
        return None, actual_race_filter_values(actual)
    if actual not in ("All", "", None):
        return actual, None
    return None, None


def matches_confirmation(
    record: Dict[str, Any],
    review: Optional[str],
    *,
    reviewed_keys: Optional[Set[str]] = None,
) -> bool:
    """True when *record* matches the Verification/confirmation filter key."""
    if review is None or review in ("", "all", "*"):
        return True
    key = str(review).strip().lower()
    if key in ("unreviewed", "unverified", "none", "unset"):
        return not is_person_reviewed(record, reviewed_keys)
    return ethnicity_review_verdict(record) == key


def filter_suspected_misclass(
    records: List[Dict[str, Any]],
    *,
    min_confidence: float = 0.5,
    ethnic_db: Any = None,
    ethnicity_review: Optional[str] = None,
    reviewed_keys: Optional[Set[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Keep only rows where the ethnic surname model disagrees with stated race.

    Same core rules as ``ArrestSearcher.analyze_ethnicities`` (min confidence,
    not compatible with recorded race). When *ethnicity_review* is set (e.g.
    ``unreviewed``), confirmed people (including identity siblings) are excluded
    and the list is person-deduped so one person is not shown multiple times.
    """
    from scraper.searcher_appearance import apply_appearance_signals
    from scraper.searcher_names import (
        _first_name_from_record,
        _last_name_from_record,
        _middle_name_from_record,
    )
    from scraper.searcher_race import _ethnicity_family, _is_compatible

    if ethnic_db is None:
        from scraper.ethnic_names import EthnicNameDatabase

        ethnic_db = EthnicNameDatabase()

    review = (ethnicity_review or "").strip().lower()
    if reviewed_keys is None and review in ("unreviewed", "unverified", "none", "unset"):
        # Best-effort: derive from the current batch (caller may pass full-DB keys).
        from scraper.identity_review import strong_identity_keys

        reviewed_keys = set()
        for rec in records:
            if ethnicity_review_verdict(rec):
                reviewed_keys.update(strong_identity_keys(rec))

    out: List[Dict[str, Any]] = []
    for rec in records:
        if not matches_confirmation(rec, ethnicity_review, reviewed_keys=reviewed_keys):
            continue
        last = _last_name_from_record(rec)
        if not last:
            continue
        first = _first_name_from_record(rec)
        middle = _middle_name_from_record(rec)
        recorded_race = (rec.get("race") or "").strip()
        recorded_eth = (rec.get("ethnicity") or "").strip() or None
        likely, conf, matching = ethnic_db.classify_by_name(
            last,
            first_name=first or None,
            middle_name=middle or None,
        )
        if conf < min_confidence or likely == "Unknown":
            continue
        if _is_compatible(likely, recorded_race, recorded_eth):
            continue
        # Eye/hair parity with analyze_ethnicities (light phenotype can drop).
        rec = dict(rec)
        conf, matching, _meta = apply_appearance_signals(
            rec,
            likely,
            conf,
            matching,
            family=_ethnicity_family(likely),
        )
        if conf < min_confidence:
            continue
        # Annotate for Actual race column / sidebar when unset or model-driven.
        rec["likely_ethnicity"] = likely
        rec["name_confidence"] = conf
        out.append(rec)
    out = dedupe_records_by_person(out, prefer_confidence=True)
    out.sort(key=lambda r: float(r.get("name_confidence") or 0), reverse=True)
    return out