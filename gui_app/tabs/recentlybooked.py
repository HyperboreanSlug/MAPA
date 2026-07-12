"""RecentlyBooked live feed, misclassify, and full scrape."""
from __future__ import annotations

import threading
from typing import Any, Dict, List

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _stretch_columns,
    _tree_frame,
)
from scraper.database import Database
from scraper.recentlybooked import RecentlyBookedScraper
from scraper.searcher import ArrestSearcher, _is_compatible, format_race_label


class RecentlyBookedTabMixin:
    def _build_recentlybooked(self, tab):
        tab.configure(fg_color=C["surface"])
        view = ctk.CTkTabview(
            tab,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
        )
        view.pack(fill="both", expand=True, padx=6, pady=6)
        host = LazyTabHost(view)
        host.register("Live Feed", self._build_rb_live)
        host.register("Misclassify", self._build_rb_misclassify)
        host.register("Full Scrape", self._build_rb_full)
        view.set("Live Feed")
        host.ensure("Live Feed")
        return host

    def _build_rb_live(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        ctk.CTkButton(bar, text="Refresh", command=self._rb_refresh).pack(
            side="left", padx=5, pady=8
        )
        ctk.CTkButton(
            bar, text="Import selected", command=lambda: self._rb_import(False)
        ).pack(side="left", padx=5)
        ctk.CTkButton(
            bar, text="Import all", command=lambda: self._rb_import(True)
        ).pack(side="left", padx=5)
        wrap, self.rb_tree = _tree_frame(tab)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ["name", "race", "state", "county", "charge", "hint"]
        self.rb_tree.configure(columns=cols)
        _enable_tree_column_sort(self.rb_tree, cols)
        _stretch_columns(self.rb_tree, cols)
        self._rb_records: List[Dict[str, Any]] = []

    def _rb_refresh(self):
        def work():
            try:
                with RecentlyBookedScraper(
                    delay=float(self.app_settings.get("rb_delay") or 1.0)
                ) as s:
                    rows = s.scrape_live(
                        with_photos=bool(self.app_settings.get("rb_with_photos", True)),
                        with_html=bool(self.app_settings.get("rb_with_html", True)),
                    )
                self.after(0, lambda: self._rb_show(rows))
            except Exception as e:
                self.log(f"Live feed failed: {e}")

        threading.Thread(target=work, daemon=True).start()

    def _rb_show(self, rows: List[Dict[str, Any]]):
        self._rb_records = rows
        self.rb_tree.delete(*self.rb_tree.get_children())
        eth = ArrestSearcher(self.db_path).ethnic_db
        for r in rows:
            n = (
                r.get("full_name")
                or f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip()
            )
            last = (r.get("last_name") or "").strip()
            if not last and n:
                last = n.split()[-1]
            first = (r.get("first_name") or "").strip() or None
            likely, conf, _ = eth.classify_by_name(last, first_name=first)
            race = r.get("race") or ""
            hint = f"{likely} {conf:.0%}"
            if likely != "Unknown" and race and not _is_compatible(likely, race, r.get("ethnicity")):
                hint = f"FLAG {hint} vs {format_race_label(race)}"
            self.rb_tree.insert(
                "",
                "end",
                values=(
                    n,
                    race,
                    r.get("state") or "",
                    r.get("county") or "",
                    (r.get("charge_description") or "")[:40],
                    hint,
                ),
            )
        self.log(f"Live feed: {len(rows)} records.")

    def _rb_import(self, all_rows: bool):
        if not self._rb_records:
            self.log("No live-feed rows to import.")
            return
        if all_rows:
            rows = list(self._rb_records)
        else:
            indexes = [self.rb_tree.index(i) for i in self.rb_tree.selection()]
            rows = [self._rb_records[i] for i in indexes if 0 <= i < len(self._rb_records)]
        r = self.db.import_records(rows, skip_existing_urls=True)
        self.log(
            f"RecentlyBooked import: +{r['imported']}, {r['skipped']} skipped."
        )
        self._refresh_db_status()

    def _build_rb_misclassify(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(
            bar,
            text="Surname misclass scoped to source_system=recentlybooked",
            font=FONT_SM,
            text_color=C["muted"],
        ).pack(side="left", padx=8, pady=8)
        ctk.CTkButton(bar, text="Analyze", command=self._rb_analyze).pack(
            side="left", padx=5
        )
        wrap, self.rb_mc_tree = _tree_frame(tab)
        wrap.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ["name", "race", "likely", "conf", "charge", "state"]
        self.rb_mc_tree.configure(columns=cols)
        _enable_tree_column_sort(self.rb_mc_tree, cols)
        _stretch_columns(self.rb_mc_tree, cols)

    def _rb_analyze(self):
        def work():
            s = ArrestSearcher(self.db_path)
            try:
                rows, base = s.analyze_ethnicities(
                    source_system="recentlybooked",
                    return_base_count=True,
                )
            finally:
                s.close()

            def fill():
                self.rb_mc_tree.delete(*self.rb_mc_tree.get_children())
                for mc in rows:
                    rec = mc.record or {}
                    name = (
                        f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
                    ).strip() or rec.get("full_name") or "—"
                    self.rb_mc_tree.insert(
                        "",
                        "end",
                        values=(
                            name,
                            mc.expected_race,
                            mc.likely_ethnicity,
                            f"{mc.confidence:.2f}",
                            (rec.get("charge_description") or "")[:36],
                            rec.get("state") or "",
                        ),
                    )
                self.log(
                    f"RecentlyBooked surname analysis: {len(rows)} flags from {base} names."
                )

            self.after(0, fill)

        threading.Thread(target=work, daemon=True).start()

    def _build_rb_full(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        self.rb_state = ctk.CTkEntry(bar, placeholder_text="State (e.g. nj)", width=80)
        self.rb_county = ctk.CTkEntry(
            bar, placeholder_text="County slug (optional)", width=160
        )
        self.rb_state.pack(side="left", padx=5, pady=8)
        self.rb_county.pack(side="left", padx=5)
        self.rb_all = ctk.CTkCheckBox(bar, text="All states")
        self.rb_all.pack(side="left", padx=5)
        self.rb_cancel = False
        ctk.CTkButton(bar, text="Start", command=self._rb_full_start).pack(
            side="left", padx=5
        )
        ctk.CTkButton(
            bar, text="Cancel", command=lambda: setattr(self, "rb_cancel", True)
        ).pack(side="left", padx=5)
        ctk.CTkLabel(
            tab,
            text="Saves detail HTML + photos by default (Settings → RecentlyBooked).",
            font=FONT_SM,
            text_color=C["muted"],
        ).pack(anchor="w", padx=12, pady=4)

    def _rb_full_start(self):
        self.rb_cancel = False
        state = self.rb_state.get().strip()
        county = self.rb_county.get().strip()
        db_path = self.db_path
        delay = float(self.app_settings.get("rb_delay") or 1.0)
        with_photos = bool(self.app_settings.get("rb_with_photos", True))
        with_html = bool(self.app_settings.get("rb_with_html", True))
        scrape_all = bool(self.rb_all.get())

        def work():
            try:
                db = Database(db_path)
                try:
                    known = db.existing_source_urls()
                    with RecentlyBookedScraper(delay=delay) as s:
                        kw = dict(
                            with_photos=with_photos,
                            with_html=with_html,
                            skip_existing_urls=known,
                            cancel_check=lambda: self.rb_cancel,
                            progress_cb=lambda n, _: self.log(
                                f"RecentlyBooked: {n} records"
                            ),
                        )
                        if scrape_all:
                            rows = s.scrape_all(**kw)
                        elif county:
                            rows = s.scrape_county(state, county, **kw)
                        elif state:
                            rows = s.scrape_state(state, **kw)
                        else:
                            self.log("Enter a state or enable All states.")
                            return
                    r = db.import_records(rows, skip_existing_urls=True)
                finally:
                    db.close()
                self.log(f"RecentlyBooked full scrape: +{r['imported']} imported.")
                self.after(0, self._refresh_db_status)
            except Exception as e:
                self.log(f"RecentlyBooked scrape failed: {e}")

        threading.Thread(target=work, daemon=True).start()
