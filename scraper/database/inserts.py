"""Insert / import / update arrest rows."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

from scraper.database.constants import _ARREST_COLUMNS, _INSERT_SQL, _to_tuple


class InsertMixin:
    def insert_arrest(self, record: Dict[str, Any]) -> int:
        cur = self._conn.cursor()
        cur.execute(_INSERT_SQL, _to_tuple(record))
        self._conn.commit()
        return int(cur.lastrowid)

    def insert_arrests_batch(self, records: List[Dict[str, Any]]) -> int:
        if not records:
            return 0
        cur = self._conn.cursor()
        cur.executemany(_INSERT_SQL, [_to_tuple(r) for r in records])
        self._conn.commit()
        n = cur.rowcount
        return n if n is not None and n >= 0 else len(records)

    def import_records(
        self,
        records: List[Dict[str, Any]],
        *,
        skip_existing_urls: bool = True,
        skip_identity_duplicates: bool = False,
        require_photo: bool = False,
    ) -> Dict[str, int]:
        from scraper.charge_classifications import classify_record
        from scraper.mugshot_ethnicity.photo_quality import record_has_real_photo
        from scraper.mugshot_sources import identity_keys_for_record

        originals: List[Dict[str, Any]] = [
            r for r in (records or []) if isinstance(r, dict)
        ]
        prepared = [dict(r) for r in originals]
        for rec in prepared:
            classify_record(rec)
        total = len(prepared)
        skipped = 0
        skipped_identity = 0
        rejected_no_photo = 0
        kept_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        existing = self.existing_source_urls() if skip_existing_urls else set()
        identity_keys: set = set()
        if skip_identity_duplicates:
            try:
                identity_keys = self.existing_identity_keys()
            except Exception:
                identity_keys = set()

        for original, rec in zip(originals, prepared):
            url = (rec.get("source_url") or rec.get("source_id") or "").strip()
            if skip_existing_urls and url and url in existing:
                skipped += 1
                continue
            if skip_identity_duplicates:
                keys = identity_keys_for_record(rec)
                if keys and any(k in identity_keys for k in keys):
                    skipped_identity += 1
                    skipped += 1
                    if url:
                        existing.add(url)
                    continue
            if require_photo and not record_has_real_photo(rec):
                rejected_no_photo += 1
                continue
            if url:
                existing.add(url)
            for k in identity_keys_for_record(rec):
                identity_keys.add(k)
            kept_pairs.append((original, rec))

        imported = 0
        if not kept_pairs:
            pass
        elif len(kept_pairs) == 1:
            # Single-row path returns id onto the caller's dict (GUI live import).
            original, rec = kept_pairs[0]
            for key in ("charge_category", "likely_ethnicity", "name_confidence"):
                if key in rec:
                    original[key] = rec[key]
            rid = self.insert_arrest(rec)
            original["id"] = int(rid)
            imported = 1
        else:
            for original, rec in kept_pairs:
                for key in ("charge_category", "likely_ethnicity", "name_confidence"):
                    if key in rec:
                        original[key] = rec[key]
            imported = self.insert_arrests_batch([rec for _, rec in kept_pairs])
        if imported:
            try:
                from scraper.db_publish_pending import add_pending_listings

                add_pending_listings(int(imported))
            except Exception:
                pass
        return {
            "imported": imported,
            "skipped": skipped,
            "skipped_identity": skipped_identity,
            "rejected_no_photo": rejected_no_photo,
            "total_rows": total,
        }

    def delete_arrests_without_real_photos(
        self, *, source_system: Optional[str] = None
    ) -> int:
        """Remove arrests missing a real mugshot file (or that only have a placeholder).

        When *source_system* is set, only that source is cleaned (e.g. recentlybooked).
        """
        from scraper.mugshot_ethnicity.photo_quality import (
            is_placeholder_photo,
            record_has_real_photo,
        )

        if source_system:
            rows = self._conn.execute(
                "SELECT id, photo_path, photo_url FROM arrests "
                "WHERE source_system = ?",
                (source_system,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, photo_path, photo_url FROM arrests"
            ).fetchall()
        from scraper.mugshot_ethnicity.photo_quality import resolve_photo_path

        delete_ids: List[int] = []
        for row in rows:
            rec = dict(row)
            if record_has_real_photo(rec):
                continue
            delete_ids.append(int(rec["id"]))
            path = str(rec.get("photo_path") or "").strip()
            if path:
                p = resolve_photo_path(path) or Path(path)
                try:
                    if p.is_file() and is_placeholder_photo(p):
                        p.unlink()
                except OSError:
                    pass
        if not delete_ids:
            return 0
        chunk = 400
        for i in range(0, len(delete_ids), chunk):
            part = delete_ids[i : i + chunk]
            ph = ",".join("?" * len(part))
            self._conn.execute(f"DELETE FROM arrests WHERE id IN ({ph})", part)
        self._conn.commit()
        return len(delete_ids)

    def reclassify_charges(self) -> int:
        from scraper.charge_classifications import classify_charge

        rows = self._conn.execute(
            "SELECT id, charge_description, charge_group, charge_level, "
            "charge_class, statute FROM arrests"
        ).fetchall()
        n = 0
        for row in rows:
            d = dict(row)
            cat = classify_charge(d)
            self._conn.execute(
                "UPDATE arrests SET charge_category = ? WHERE id = ?",
                (cat, d["id"]),
            )
            n += 1
        self._conn.commit()
        return n

    def update_arrest(self, row_id: int, fields: Dict[str, Any]) -> bool:
        if not fields:
            return False
        allowed = set(_ARREST_COLUMNS) | {"scraped_at"}
        cols = [k for k in fields if k in allowed]
        if not cols:
            return False
        sets = ", ".join(f"{c} = ?" for c in cols)
        vals = [fields[c] for c in cols]
        vals.append(int(row_id))
        cur = self._conn.execute(f"UPDATE arrests SET {sets} WHERE id = ?", vals)
        self._conn.commit()
        if (cur.rowcount or 0) > 0:
            return True
        # SQLite may report 0 when values are unchanged — still success if row exists.
        exists = self._conn.execute(
            "SELECT 1 FROM arrests WHERE id = ?", (int(row_id),)
        ).fetchone()
        return exists is not None

    # SOR DeepFace UI alias
    def update_offender(self, row_id: int, fields: Dict[str, Any]) -> bool:
        return self.update_arrest(row_id, fields)
