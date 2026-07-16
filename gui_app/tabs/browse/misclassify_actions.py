"""Browse tab refresh, verdict, actual-race actions."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from gui_app.shared.record_sidebar import merge_race_manual_flags
from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_ACTUAL_RACES,
    bucket_actual_race,
)
from gui_app.tabs.browse.misclassify_suspect import (
    filter_suspected_misclass,
    resolve_actual_filter,
)
from gui_app.tabs.browse.misclassify_verdict import apply_browse_verdict
from gui_app.widgets import tree_iid_for_record, tree_row_bind, tree_rows_reset
from scraper.database import Database


class MisclassifyActionsMixin:
    def _browse_refresh(self):
        if getattr(self, "_browse_busy", False):
            return
        self._browse_busy = True
        try:
            self.browse_refresh_btn.configure(state="disabled")
        except Exception:
            pass
        self.browse_status.configure(text="Loading…")
        stated = self.browse_stated_race.get()
        review_q = self._browse_verification_query(self.browse_review.get())
        raw_limit = (self.browse_limit.get() or "").strip()
        try:
            limit = max(0, int(raw_limit) if raw_limit else 0)
        except ValueError:
            limit = 0
        misclass_only = bool(
            getattr(self, "browse_misclass_only", None)
            and self.browse_misclass_only.get()
        )
        likely_one, likely_in = resolve_actual_filter(
            self.browse_actual_race_filter.get()
        )
        fetch_limit = 0 if misclass_only else limit

        def work():
            try:
                db = Database(self.db_path)
                try:
                    from scraper.identity_review import load_reviewed_identity_keys

                    reviewed_keys = (
                        load_reviewed_identity_keys(db)
                        if review_q in ("unreviewed", "unverified", "none", "unset")
                        else None
                    )
                    rows = db.search_records(
                        race=None if stated in ("All", "", None) else stated,
                        likely_ethnicity=likely_one,
                        likely_ethnicity_in=likely_in,
                        ethnicity_review=review_q,
                        limit=fetch_limit,
                    )
                    if misclass_only:
                        # Confirmed people (and siblings) stay out of Unverified.
                        rows = filter_suspected_misclass(
                            rows,
                            ethnicity_review=review_q,
                            reviewed_keys=reviewed_keys,
                        )
                        if limit:
                            rows = rows[:limit]
                finally:
                    db.close()
                self.after(
                    0,
                    lambda r=rows, lim=limit, m=misclass_only: self._browse_show(
                        r, limit=lim, misclass_only=m
                    ),
                )
            except Exception as exc:
                self.after(0, lambda e=exc: self._browse_error(e))

        threading.Thread(target=work, daemon=True).start()

    def _browse_error(self, exc: Exception):
        self._browse_busy = False
        self.browse_refresh_btn.configure(state="normal")
        self.browse_status.configure(text=f"Browse failed: {exc}")

    def _browse_show(
        self,
        rows: List[Dict[str, Any]],
        limit: int = 0,
        total_hint: Optional[int] = None,
        misclass_only: bool = False,
    ):
        self._browse_records = list(rows)
        self._mc_results = self._browse_records
        self.mc_tree.delete(*self.mc_tree.get_children())
        tree_rows_reset(self.mc_tree)
        for rec in self._browse_records:
            item = self.mc_tree.insert("", "end", values=self._browse_row_values(rec))
            tree_row_bind(self.mc_tree, item, rec)
        self._browse_busy = False
        self.browse_refresh_btn.configure(state="normal")
        n = len(self._browse_records)
        kind = "suspected misclassifications" if misclass_only else "arrests"
        msg = f"{n:,} {kind}"
        if limit and n >= limit:
            msg += f" (limit {limit:,} — set Limit to 0 for all)"
        self.browse_status.configure(text=msg)
        self.browse_sidebar.clear("Select a row for photo and review.")

    def _browse_find_index(self, record: Dict[str, Any]) -> Optional[int]:
        rid, url = record.get("id"), str(record.get("source_url") or "")
        for i, existing in enumerate(self._browse_records):
            if rid is not None and existing.get("id") == rid:
                return i
            if url and existing.get("source_url") == url:
                return i
        return None

    def _browse_related_indexes(self, record: Dict[str, Any]) -> List[int]:
        """Indexes of this row and any identity siblings still in the list."""
        from scraper.identity_review import shares_identity

        sib_ids = {
            int(x)
            for x in (record.get("_confirmed_sibling_ids") or [])
            if x is not None
        }
        rid = record.get("id")
        if rid is not None:
            sib_ids.add(int(rid))
        out: List[int] = []
        for i, existing in enumerate(self._browse_records):
            eid = existing.get("id")
            if eid is not None and int(eid) in sib_ids:
                out.append(i)
                continue
            if shares_identity(record, existing):
                out.append(i)
        if not out:
            idx = self._browse_find_index(record)
            if idx is not None:
                out.append(idx)
        return out

    def _browse_sync_row(self, record: Dict[str, Any], *, drop: bool) -> None:
        indexes = self._browse_related_indexes(record)
        if not indexes:
            return
        if drop:
            # Drop highest index first so earlier indices stay valid.
            for idx in sorted(indexes, reverse=True):
                self._browse_drop_row(idx)
            return
        idx = indexes[0]
        rec = self._browse_records[idx]
        for key in ("flags", "likely_ethnicity", "id"):
            if record.get(key) is not None:
                rec[key] = record.get(key)
        iid = tree_iid_for_record(self.mc_tree, rec)
        if iid is not None:
            self.mc_tree.item(iid, values=self._browse_row_values(rec))
        self.browse_sidebar.show(rec)

    def _browse_sidebar_verdict(self, record: Dict[str, Any], verdict: str):
        label = (
            "confirmed correct" if verdict == "correct" else "confirmed incorrect"
        )
        ok, err, record = apply_browse_verdict(
            db_path=self.db_path,
            db=getattr(self, "db", None),
            record=record,
            verdict=verdict,
        )
        if not ok:
            self.browse_status.configure(
                text=f"Could not save verification: {err or 'unknown error'}"
            )
            self.log(f"Browse verification save failed: {err}")
            return
        if err:
            self.log(f"Browse verification warning: {err}")
        want = self._browse_verification_query(self.browse_review.get())
        drop = (
            (want == "correct" and verdict != "correct")
            or (want == "incorrect" and verdict != "incorrect")
            or (want == "unreviewed")
        )
        self._browse_sync_row(record, drop=drop)
        extra = (
            f" · actual={record.get('likely_ethnicity')}"
            if verdict == "correct" and record.get("likely_ethnicity")
            else ""
        )
        name = self._browse_name(record)
        msg = f"Saved {name} as {label}{extra}. {len(self._browse_records):,} shown."
        self.browse_status.configure(text=msg)
        self.log(f"Browse verification: {name} → {label}{extra} (saved)")

    def _browse_sidebar_actual_race(self, record: Dict[str, Any], actual: str):
        from gui_app.shared.record_sidebar_flags import verdict_for_actual_vs_stated
        from gui_app.shared.verdict_persist import persist_ethnicity_verdict

        raw = (actual or "").strip() or "Unknown"
        actual = bucket_actual_race(raw) or raw
        if actual not in BROWSE_ACTUAL_RACES and raw in BROWSE_ACTUAL_RACES:
            actual = raw
        record["likely_ethnicity"] = actual
        # Choosing actual race confirms classification (leave Unverified queue).
        verdict = verdict_for_actual_vs_stated(record.get("race"), actual)
        ok, _flags, err = persist_ethnicity_verdict(
            self.db_path,
            record,
            verdict,
            extra_fields={"likely_ethnicity": actual},
        )
        flags_json = merge_race_manual_flags(record.get("flags"))
        record["flags"] = flags_json
        rid = record.get("id")
        try:
            if rid is not None:
                self.db.update_arrest(
                    int(rid), {"likely_ethnicity": actual, "flags": flags_json}
                )
            for sid in record.get("_confirmed_sibling_ids") or []:
                if rid is not None and int(sid) == int(rid):
                    continue
                row = self.db._conn.execute(
                    "SELECT flags FROM arrests WHERE id = ?", (int(sid),)
                ).fetchone()
                raw_f = row["flags"] if row else flags_json
                self.db.update_arrest(
                    int(sid),
                    {
                        "likely_ethnicity": actual,
                        "flags": merge_race_manual_flags(raw_f),
                    },
                )
        except Exception as exc:
            self.browse_status.configure(text=f"Could not save actual race: {exc}")
            return
        if not ok and err:
            self.log(f"Browse actual race confirm warn: {err}")
        want_race = (self.browse_actual_race_filter.get() or "All").strip()
        race_mismatch = want_race not in ("All", "", None) and (
            bucket_actual_race(want_race) or want_race
        ) != (bucket_actual_race(actual) or actual)
        want_review = self._browse_verification_query(self.browse_review.get())
        drop = race_mismatch or (ok and want_review == "unreviewed")
        self._browse_sync_row(record, drop=drop)
        conf = f", confirmed {verdict}" if ok else ""
        self.browse_status.configure(
            text=(
                f"Actual race set to {actual}{conf}. "
                f"{len(self._browse_records):,} shown."
            )
        )
        self.log(f"Browse actual race: {self._browse_name(record)} → {actual}{conf}")
