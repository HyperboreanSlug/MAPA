"""Browse refresh. Load rows in a thread."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

from gui_app.tabs.browse.misclassify_constants import (
    BROWSE_DEFAULT_LIMIT,
    BROWSE_HARD_MAX,
)
from gui_app.tabs.browse.misclassify_suspect import (
    filter_suspected_misclass,
    resolve_actual_filter,
)
from gui_app.widgets import tree_rows_reset, tree_row_bind
from scraper.database import Database


class MisclassifyRefreshMixin:
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
            parsed = max(0, int(raw_limit) if raw_limit else BROWSE_DEFAULT_LIMIT)
        except ValueError:
            parsed = BROWSE_DEFAULT_LIMIT
        # 0 = "all" but never unbounded in the GUI (2M+ DOC rows OOM the process).
        unlimited_requested = parsed == 0
        limit = BROWSE_HARD_MAX if unlimited_requested else min(parsed, BROWSE_HARD_MAX)
        misclass_only = bool(
            getattr(self, "browse_misclass_only", None)
            and self.browse_misclass_only.get()
        )
        photo_only = bool(
            getattr(self, "browse_photo_only", None)
            and self.browse_photo_only.get()
        )
        likely_one, likely_in = resolve_actual_filter(
            self.browse_actual_race_filter.get()
        )
        # Read all Tk state here. Worker must not call widget get.
        try:
            since_main = self._browse_since_date() if hasattr(self, "_browse_since_date") else None
        except Exception:
            since_main = None
        try:
            src_main = (self.browse_source_filter.get() or "All").strip() if getattr(self, "browse_source_filter", None) is not None else "All"
        except Exception:
            src_main = "All"
        # Over-fetch for misclass filter; still hard-capped for memory safety.
        fetch_limit = (
            min(BROWSE_HARD_MAX, max(limit * 20, 2000)) if misclass_only else limit
        )

        def work(since=since_main, src=src_main):
            try:
                db = Database(self.db_path)
                try:
                    from scraper.identity_review import load_reviewed_identity_keys

                    reviewed_keys = (
                        load_reviewed_identity_keys(db)
                        if review_q in ("unreviewed", "unverified", "none", "unset")
                        else None
                    )
                    since = since
                    src = src
                    rows = db.search_records(
                        race=None if stated in ("All", "", None) else stated,
                        likely_ethnicity=likely_one,
                        likely_ethnicity_in=likely_in,
                        ethnicity_review=review_q,
                        source_system=None if src in ("All", "", None) else src,
                        since_date=since,
                        photo_only=photo_only,
                        limit=fetch_limit,
                    )
                    if misclass_only:
                        # Confirmed people (and siblings) stay out of Unverified.
                        rows = filter_suspected_misclass(
                            rows,
                            ethnicity_review=review_q,
                            reviewed_keys=reviewed_keys,
                        )
                        rows = rows[:limit]
                finally:
                    db.close()
                self.after(
                    0,
                    lambda r=rows, lim=limit, m=misclass_only, u=unlimited_requested: self._browse_show(
                        r, limit=lim, misclass_only=m, unlimited_requested=u
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
        unlimited_requested: bool = False,
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
        if unlimited_requested and limit and n >= limit:
            msg += f" (capped at {limit:,} for memory safety)"
        elif limit and n >= limit:
            msg += f" (limit {limit:,})"
        try:
            if hasattr(self, "_browse_since_date") and self._browse_since_date():
                amt = ""
                unit = "days"
                if getattr(self, "browse_window_amount", None) is not None:
                    amt = (self.browse_window_amount.get() or "").strip()
                if getattr(self, "browse_window_unit", None) is not None:
                    unit = (self.browse_window_unit.get() or "days").strip()
                if amt:
                    msg += f" · last {amt} {unit}"
        except Exception:
            pass
        self.browse_status.configure(text=msg)
        self.browse_sidebar.clear("Select a row for photo and review.")

