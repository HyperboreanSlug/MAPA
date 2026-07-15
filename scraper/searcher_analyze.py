"""Ethnic misclassification analysis loop for ArrestSearcher."""
from __future__ import annotations

from typing import List, Optional

from .searcher_core import Misclassification
from .searcher_names import (
    _first_name_from_record,
    _last_name_from_record,
    _middle_name_from_record,
    ethnicity_review_verdict,
)
from .searcher_race import _ethnicity_family, _is_compatible, format_race_label


def _normalize_review_filter(ethnicity_review: Optional[str]) -> Optional[str]:
    """Map UI/CLI review label → unreviewed | correct | incorrect | None (all)."""
    raw = (ethnicity_review if ethnicity_review is not None else "unreviewed")
    key = str(raw).strip().lower()
    if key in ("", "all", "*"):
        return None
    if key in ("unreviewed", "none", "unset", "unverified"):
        return "unreviewed"
    if key in ("correct", "confirmed correct"):
        return "correct"
    if key in ("incorrect", "confirmed incorrect"):
        return "incorrect"
    return "unreviewed"


def analyze_ethnicities_impl(
    searcher,
    min_confidence: float = 0.5,
    limit: int = 0,
    ethnicity_filter: Optional[str] = None,
    charge_category: Optional[str] = None,
    source_system: Optional[str] = None,
    race: Optional[str] = None,
    return_base_count: bool = False,
    named_only: bool = True,
    ethnicity_review: Optional[str] = "unreviewed",
):
    """Primary analysis: surname ethnicity vs recorded race on arrest rows.

    *ethnicity_review* defaults to ``unreviewed`` so confirmed rows never reappear
    in the default queue. Pass ``all`` / ``None`` to include confirmed, or
    ``correct`` / ``incorrect`` to list only that confirmation status.
    """
    from .charge_classifications import classify_charge

    misclassifications: List[Misclassification] = []
    base_count = 0
    filter_key = (ethnicity_filter or "").strip().lower() or None
    charge_f = (charge_category or "").strip().lower() or None
    if charge_f in ("all", "*", ""):
        charge_f = None
    src_f = (source_system or "").strip().lower() or None
    if src_f in ("all", "*", ""):
        src_f = None
    race_f = (race or "").strip() or None
    if race_f and race_f.lower() in ("all", "*", ""):
        race_f = None
    race_label_f = format_race_label(race_f) if race_f else None
    review_f = _normalize_review_filter(ethnicity_review)
    hc_only = filter_key in (
        "indian_high_confidence",
        "high_confidence_indian",
        "high-confidence indian",
        "indian_hc",
    )
    family_filter = "indian" if hc_only else filter_key
    scan_limit = None if limit is None or int(limit) <= 0 else int(limit)
    newest_first = bool(scan_limit)

    for record in searcher.db.iter_arrests(
        limit=scan_limit,
        newest_first=newest_first,
        named_only=named_only,
        charge_category=charge_f,
        source_system=src_f,
    ):
        verdict = ethnicity_review_verdict(record)
        if review_f == "unreviewed":
            if verdict:
                continue
        elif review_f is not None and verdict != review_f:
            continue
        if charge_f:
            cat = (record.get("charge_category") or "").strip().lower()
            if not cat or cat == "unknown":
                cat = classify_charge(record)
                record["charge_category"] = cat
            if cat != charge_f:
                continue
        last_name = _last_name_from_record(record)
        first_name = _first_name_from_record(record)
        middle_name = _middle_name_from_record(record)
        recorded_race = (record.get("race") or "").strip()
        recorded_ethnicity = (record.get("ethnicity") or "").strip() or None
        if not last_name:
            continue
        if race_label_f is not None:
            if format_race_label(recorded_race) != race_label_f:
                continue
        if hc_only and not searcher.ethnic_db.is_indian_high_confidence_surname(last_name):
            continue
        likely_eth, confidence, matching_names = searcher.ethnic_db.classify_by_name(
            last_name,
            first_name=first_name or None,
            middle_name=middle_name or None,
        )
        if confidence < min_confidence or likely_eth == "Unknown":
            continue
        family = _ethnicity_family(likely_eth)
        if family_filter and family != family_filter:
            continue
        base_count += 1
        if _is_compatible(likely_eth, recorded_race, recorded_ethnicity):
            continue
        # Eye/hair (e.g. brown eyes + brown hair) corroborates or weakens
        from .searcher_appearance import apply_appearance_signals

        confidence, matching_names, _meta = apply_appearance_signals(
            record,
            likely_eth,
            confidence,
            matching_names,
            family=family,
        )
        if confidence < min_confidence:
            continue
        if not record.get("charge_category"):
            record["charge_category"] = classify_charge(record)
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
