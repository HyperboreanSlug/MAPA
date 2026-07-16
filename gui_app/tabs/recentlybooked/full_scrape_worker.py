"""RecentlyBooked Full Scrape background worker."""
from __future__ import annotations

import threading
import time as _time
from typing import Any, Dict

from scraper.database import Database
from scraper.searcher import ArrestSearcher

from .constants import _RB_AVAILABLE_SOURCE_IDS
from .full_scrape_ui import _full_import_row


class RbFullScrapeWorkerMixin:
    def _rb_full_scrape_worker(self, cfg: Dict[str, Any]) -> None:
        source_id = cfg["source_id"]
        source_label = cfg["source_label"]
        workers = cfg["workers"]
        counters = {"imported": 0, "skipped": 0, "rejected": 0}
        scrape_warning = None
        import_lock = threading.Lock()
        try:
            eth = ArrestSearcher(cfg["db_path"]).ethnic_db
            self._rb_full_eth = eth
            db = Database(cfg["db_path"])
            try:
                purge_ids = (
                    list(_RB_AVAILABLE_SOURCE_IDS)
                    if source_id == "all"
                    else [source_id]
                )
                for sid in purge_ids:
                    try:
                        purged = db.delete_arrests_without_real_photos(
                            source_system=sid
                        )
                        if purged:
                            self.log_full(
                                f"Full scrape: deleted {purged} "
                                f"{sid} arrests without a real photo."
                            )
                    except Exception as exc:
                        self.log_full(f"Full scrape purge ({sid}) skipped: {exc}")
                known = db.existing_source_urls()
                self._rb_full_last_loc = ""
                self.log_full(
                    f"{source_label}: {len(known):,} known URL(s) in DB "
                    f"(will skip duplicates)."
                )

                def on_record(rec: Dict[str, Any], n: int) -> None:
                    if getattr(self, "_closing", False):
                        return
                    row = dict(rec)
                    err = _full_import_row(row, db, known, counters, import_lock)
                    if err:
                        self.after(
                            0,
                            lambda e=err, u=str(row.get("source_url") or ""): self.log_full(
                                f"{source_label} store failed ({u}): {e}"
                            ),
                        )
                    loc = str(row.get("_scrape_loc") or "")
                    self.after(
                        0,
                        lambda r=row, nn=n, lc=loc: self._rb_full_ui_append(
                            r,
                            eth=eth,
                            n=nn,
                            counters=counters,
                            workers=workers,
                            source_label=source_label,
                            scrape_loc=lc,
                        ),
                    )

                _prog_t = [0.0]

                def on_progress(count, _total=None, context=None):
                    if getattr(self, "_closing", False):
                        return
                    now = _time.time()
                    # Always refresh status when location changes; else throttle logs.
                    loc = ""
                    if isinstance(context, dict):
                        loc = str(context.get("label") or "")
                    force = bool(loc and loc != getattr(self, "_rb_full_last_loc", ""))
                    # Errors / empty-catalog messages always surface immediately.
                    is_err = "error" in loc.lower() or "0 counties" in loc.lower()
                    if not force and not is_err and now - _prog_t[0] < 2.0:
                        return
                    _prog_t[0] = now
                    ctx = dict(context) if isinstance(context, dict) else None
                    self.after(
                        0,
                        lambda c=count, cx=ctx: self._rb_full_set_progress(
                            source_label=source_label,
                            count=c,
                            workers=workers,
                            counters=counters,
                            context=cx,
                        ),
                    )

                try:
                    self._rb_full_run_scraper(
                        source_id=source_id,
                        state=cfg["state"],
                        county=cfg["county"],
                        scrape_all=cfg["scrape_all"],
                        delay=cfg["delay"],
                        workers=workers,
                        with_photos=cfg["with_photos"],
                        with_html=cfg["with_html"],
                        known=known,
                        db=db,
                        on_record=on_record,
                        on_progress=on_progress,
                    )
                except Exception as scrape_exc:
                    scrape_warning = self._rb_full_scrape_error_msg(scrape_exc)
                    self.log_full(
                        f"{source_label}: scrape interrupted ({scrape_warning}). "
                        f"Keeping {counters['imported']} imported so far."
                    )
                try:
                    if source_id == "all":
                        dret = db.remove_cross_source_duplicates(
                            dry_run=False,
                            merge_fields=True,
                            source_systems=list(_RB_AVAILABLE_SOURCE_IDS),
                        )
                    else:
                        dret = db.remove_name_dob_photo_duplicates(
                            dry_run=False,
                            merge_fields=True,
                            source_system=source_id,
                        )
                    _removed = int(dret.get("deleted") or 0)
                    if _removed:
                        self.log_full(
                            f"Full scrape dedupe: removed {_removed} duplicate row(s)."
                        )
                except Exception as exc:
                    self.log_full(f"Full scrape dedupe skipped: {exc}")
            finally:
                db.close()

            cancelled = bool(getattr(self, "rb_cancel", False))
            fetched = len(getattr(self, "_rb_full_all", []) or [])
            verb = "cancelled" if cancelled else "done"
            msg = (
                f"{source_label} full scrape {verb}: "
                f"{len(self._rb_full_records)}/{fetched} shown, "
                f"+{counters['imported']} imported, {counters['skipped']} skipped, "
                f"{counters['rejected']} no-photo dropped ({workers} threads)."
            )
            if scrape_warning:
                msg += f" · interrupted: {scrape_warning}"
            if not cancelled and not scrape_warning and fetched == 0:
                msg += (
                    " · no new records (catalog empty, all known, or host blocked). "
                    "Check activity log for county/list errors."
                )
                self.log_full(
                    f"{source_label}: finished with 0 fetched records — "
                    "not a silent hang; see earlier log lines for catalog/list errors."
                )
            self.log_full(msg)
            self.after(0, lambda: self.rb_full_status.configure(text=msg))
            self.after(0, self._refresh_db_status)
        except Exception as e:
            self.log_full(f"{source_label} scrape failed: {e}")
            self.after(
                0,
                lambda: self.rb_full_status.configure(text=f"Failed: {e}"),
            )
        finally:
            self._rb_full_busy = False
            self.is_running = False
