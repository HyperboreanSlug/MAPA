"""Field-union helpers for merging duplicate arrest rows."""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from scraper.database.constants import _ARREST_COLUMNS, _MERGE_SEP, _MERGE_UNION_FIELDS


class DedupeMergeFieldsMixin:
    """Score rows and union multi-value / fill-blank fields on merge."""

    @staticmethod
    def _row_richness(row: Dict[str, Any]) -> int:
        score = 0
        for col, weight in (
            ("race", 3),
            ("charge_description", 2),
            ("last_name", 2),
            ("first_name", 1),
            ("source_url", 2),
            ("arrest_date", 1),
            ("booking_date", 1),
            ("agency", 1),
            ("state", 1),
            ("date_of_birth", 1),
            ("address", 1),
            ("charge_category", 1),
        ):
            val = row.get(col)
            if val is not None and str(val).strip():
                score += weight
                if _MERGE_SEP in str(val):
                    score += 1
        return score

    @staticmethod
    def _split_merged_values(value: Any) -> List[str]:
        raw = str(value or "").strip()
        if not raw:
            return []
        parts: List[str] = []
        seen: set = set()
        for chunk in raw.split(_MERGE_SEP):
            for piece in re.split(r"[;\n]+", chunk):
                p = " ".join(piece.strip().split())
                if not p:
                    continue
                key = p.casefold()
                if key in seen:
                    continue
                seen.add(key)
                parts.append(p)
        return parts

    @classmethod
    def _union_field_values(cls, *values: Any) -> str:
        parts: List[str] = []
        seen: set = set()
        for v in values:
            for p in cls._split_merged_values(v):
                key = p.casefold()
                if key in seen:
                    continue
                seen.add(key)
                parts.append(p)
        return _MERGE_SEP.join(parts)

    @classmethod
    def merge_duplicate_members(
        cls,
        keep: Dict[str, Any],
        losers: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Merge losers into keep: union states/charges/URLs; fill blanks."""
        if not losers:
            return {}
        updates: Dict[str, Any] = {}
        all_rows = [keep] + list(losers)

        for col in _MERGE_UNION_FIELDS:
            merged = cls._union_field_values(*(r.get(col) for r in all_rows))
            cur = str(keep.get(col) or "").strip()
            if merged and merged != cur:
                updates[col] = merged

        for col in _ARREST_COLUMNS:
            if col in _MERGE_UNION_FIELDS or col == "flags":
                continue
            if col == "raw_json":
                cur = keep.get(col)
                if cur is not None and str(cur).strip():
                    continue
                for r in losers:
                    alt = r.get(col)
                    if alt is not None and str(alt).strip():
                        updates[col] = alt
                        break
                continue
            cur = keep.get(col)
            if cur is not None and str(cur).strip():
                continue
            for r in losers:
                alt = r.get(col)
                if alt is not None and str(alt).strip():
                    updates[col] = alt
                    break

        merged_ids = []
        for r in losers:
            try:
                merged_ids.append(int(r["id"]))
            except (KeyError, TypeError, ValueError):
                pass
        # Keep-first flag merge, then fill missing keys from losers so
        # ethnicity_review / race_manual on a deleted twin is not dropped.
        flag_out = cls._merge_flags_dicts(keep, losers)
        if merged_ids:
            flag_out["merged_from_ids"] = merged_ids
            flag_out["merged_listings"] = {
                "states": cls._split_merged_values(
                    updates.get("state", keep.get("state"))
                ),
                "charges": cls._split_merged_values(
                    updates.get("charge_description", keep.get("charge_description"))
                )[:20],
                "source_urls": cls._split_merged_values(
                    updates.get("source_url", keep.get("source_url"))
                )[:20],
                "count": 1 + len(merged_ids),
            }
        if flag_out:
            try:
                updates["flags"] = json.dumps(
                    flag_out, ensure_ascii=False, sort_keys=True
                )
            except Exception:
                pass
        return updates

    @staticmethod
    def _parse_flags_dict(raw: Any) -> Dict[str, Any]:
        if isinstance(raw, dict):
            return dict(raw)
        if isinstance(raw, str) and raw.strip():
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return dict(parsed)
                return {"tags": [str(raw)]}
            except Exception:
                return {"notes": raw}
        return {}

    @classmethod
    def _merge_flags_dicts(
        cls, keep: Dict[str, Any], losers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Union flags; keep wins on conflicts; never drop ethnicity_review."""
        skip = {"merged_from_ids", "merged_listings"}
        out = cls._parse_flags_dict(keep.get("flags"))
        for r in losers:
            other = cls._parse_flags_dict(r.get("flags"))
            for key, val in other.items():
                if key in skip:
                    continue
                cur = out.get(key)
                if cur is None or cur == "" or cur is False:
                    out[key] = val
        # Explicit safeguard: confirmation verdict from any sibling.
        if not str(out.get("ethnicity_review") or "").strip():
            for r in [keep, *losers]:
                other = cls._parse_flags_dict(r.get("flags"))
                verdict = str(other.get("ethnicity_review") or "").strip().lower()
                if verdict in ("correct", "incorrect"):
                    out["ethnicity_review"] = verdict
                    at = other.get("ethnicity_reviewed_at")
                    if at:
                        out["ethnicity_reviewed_at"] = at
                    break
        return out
