"""Misclassification CSV export and searcher singleton helpers."""
from __future__ import annotations

from typing import Optional

from .searcher_core import ArrestSearcher


class ArrestSearcherExportMixin:
    """CSV export for ethnic misclassification results."""

    def export_misclassifications(
        self,
        output_path: str,
        ethnicity_filter: Optional[str] = None,
        charge_category: Optional[str] = None,
        source_system: Optional[str] = None,
        race: Optional[str] = None,
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
            source_system=source_system,
            race=race,
        )
        if not results:
            with open(output_path, "w", newline="", encoding="utf-8") as f:
                csv.writer(f).writerow(
                    [
                        "name", "recorded_race", "likely_ethnicity", "confidence",
                        "eyes", "hair", "appearance",
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
                    "eyes", "hair", "appearance", "matching_names",
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
                    "eyes": rec.get("eyes") or rec.get("eye_color") or "",
                    "hair": rec.get("hair") or rec.get("hair_color") or "",
                    "appearance": rec.get("_appearance_note") or "",
                    "matching_names": "; ".join(mc.matching_names or []),
                    "charge": rec.get("charge_description") or "",
                    "charge_category": category_label(cat) if cat else "",
                    "state": rec.get("state") or "",
                    "arrest_date": rec.get("arrest_date") or rec.get("booking_date") or "",
                    "source_system": rec.get("source_system") or "",
                    "source_url": rec.get("source_url") or "",
                })
        return len(results)


class ArrestSearcherFull(ArrestSearcherExportMixin, ArrestSearcher):
    """ArrestSearcher with export support."""


SexOffenderSearcher = ArrestSearcherFull

_searcher: Optional[ArrestSearcherFull] = None


def get_searcher(db_path: Optional[str] = None) -> ArrestSearcherFull:
    global _searcher
    if db_path is not None:
        return ArrestSearcherFull(db_path)
    if _searcher is None:
        _searcher = ArrestSearcherFull()
    return _searcher
