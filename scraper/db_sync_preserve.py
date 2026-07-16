"""Preserve local ethnic classifications when applying remote public DB sync.

Clients may confirm surname/race reviews on their machine. Remote base/delta
packages must not wipe those user decisions when rows are upserted or the
base database is replaced.

Protected signals (in ``arrests.flags`` JSON):
  - ethnicity_review / ethnicity_reviewed_at
  - race_manual / race_manual_at

When ``race_manual`` is set, the local ``race`` column is also kept.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scraper.db_sync_keys import SYNC_ROW_COLUMNS, sync_record_key

_PROTECTED_FLAG_KEYS = (
    "ethnicity_review",
    "ethnicity_reviewed_at",
    "race_manual",
    "race_manual_at",
)


def _parse_flags(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
            return dict(parsed) if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def has_user_classification(flags_raw: Any) -> bool:
    """True when the row has a local ethnicity review or manual race override."""
    flags = _parse_flags(flags_raw)
    if str(flags.get("ethnicity_review") or "").strip():
        return True
    if flags.get("race_manual"):
        return True
    return False


def extract_local_overlays(db_path: Path) -> Dict[str, Dict[str, Any]]:
    """Map sync key → overlay payload for rows with local user classifications."""
    db_path = Path(db_path)
    if not db_path.is_file():
        return {}
    conn = sqlite3.connect(f"file:{db_path.resolve().as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    out: Dict[str, Dict[str, Any]] = {}
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(arrests)")]
        if "flags" not in cols:
            return {}
        want = [c for c in ("id", "flags", "race", "likely_ethnicity", *SYNC_ROW_COLUMNS) if c in cols]
        # de-dupe while preserving order
        seen = set()
        want = [c for c in want if not (c in seen or seen.add(c))]
        sel = ", ".join(want)
        for rec in conn.execute(f"SELECT {sel} FROM arrests"):
            d = {c: rec[c] for c in want}
            if not has_user_classification(d.get("flags")):
                continue
            key = sync_record_key(d)
            flags = _parse_flags(d.get("flags"))
            overlay: Dict[str, Any] = {
                "flags": d.get("flags"),
                "protected": {k: flags.get(k) for k in _PROTECTED_FLAG_KEYS if k in flags},
            }
            if flags.get("race_manual") and d.get("race") is not None:
                overlay["race"] = d.get("race")
            # Keep user-set likely_ethnicity when present on reviewed rows.
            if d.get("likely_ethnicity"):
                overlay["likely_ethnicity"] = d.get("likely_ethnicity")
            out[key] = overlay
        return out
    except Exception:
        return {}
    finally:
        conn.close()


def merge_overlay_into_row(
    row: Dict[str, Any],
    overlay: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Return a copy of *row* with local classification fields restored."""
    if not overlay:
        return dict(row)
    out = dict(row)
    remote_flags = _parse_flags(out.get("flags"))
    protected = overlay.get("protected") or {}
    if not protected and overlay.get("flags") is not None:
        # Fall back to full local flags merge of protected keys only.
        local_flags = _parse_flags(overlay.get("flags"))
        protected = {k: local_flags.get(k) for k in _PROTECTED_FLAG_KEYS if k in local_flags}
    for k, v in protected.items():
        if v is not None:
            remote_flags[k] = v
    if protected:
        out["flags"] = json.dumps(remote_flags, ensure_ascii=False, sort_keys=True)
    if "race" in overlay and overlay["race"] is not None:
        out["race"] = overlay["race"]
    if overlay.get("likely_ethnicity"):
        # Do not overwrite remote auto-class unless local had an explicit review.
        out["likely_ethnicity"] = overlay["likely_ethnicity"]
    return out


def apply_overlays_to_db(
    db_path: Path,
    overlays: Dict[str, Dict[str, Any]],
) -> int:
    """Re-apply overlays onto matching rows after a full base install. Returns count."""
    if not overlays:
        return 0
    db_path = Path(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    n = 0
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(arrests)")]
        want = [c for c in SYNC_ROW_COLUMNS if c in cols]
        if "id" not in cols or not want:
            return 0
        sel = "id, " + ", ".join(want)
        updates: List[Tuple[Any, ...]] = []
        for rec in conn.execute(f"SELECT {sel} FROM arrests"):
            d = {"id": rec[0]}
            for i, c in enumerate(want, start=1):
                d[c] = rec[i]
            key = sync_record_key(d)
            overlay = overlays.get(key)
            if not overlay:
                continue
            merged = merge_overlay_into_row(d, overlay)
            updates.append(
                (
                    merged.get("flags"),
                    merged.get("race"),
                    merged.get("likely_ethnicity"),
                    int(d["id"]),
                )
            )
        if updates:
            conn.executemany(
                "UPDATE arrests SET flags=?, race=?, likely_ethnicity=? WHERE id=?",
                updates,
            )
            conn.commit()
            n = len(updates)
        return n
    finally:
        conn.close()


def load_local_row_overlay(
    conn: sqlite3.Connection,
    row_ids: List[int],
) -> Optional[Dict[str, Any]]:
    """Build an overlay from existing local row id(s) before delete/upsert."""
    if not row_ids:
        return None
    for rid in row_ids:
        rec = conn.execute(
            "SELECT flags, race, likely_ethnicity FROM arrests WHERE id=?",
            (int(rid),),
        ).fetchone()
        if rec is None:
            continue
        flags = rec[0] if not hasattr(rec, "keys") else rec["flags"]
        if not has_user_classification(flags):
            continue
        race = rec[1] if not hasattr(rec, "keys") else rec["race"]
        likely = rec[2] if not hasattr(rec, "keys") else rec["likely_ethnicity"]
        parsed = _parse_flags(flags)
        overlay: Dict[str, Any] = {
            "flags": flags,
            "protected": {k: parsed.get(k) for k in _PROTECTED_FLAG_KEYS if k in parsed},
        }
        if parsed.get("race_manual") and race is not None:
            overlay["race"] = race
        if likely:
            overlay["likely_ethnicity"] = likely
        return overlay
    return None
