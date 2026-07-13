"""RecentlyBooked live feed, misclassify, and full scrape."""
from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.shared.record_sidebar import RecordSidebar, merge_ethnicity_review_flags
from gui_app.theme import C, FONT_SM
from gui_app.widgets import (
    _enable_tree_column_sort,
    _hpaned,
    _stretch_columns,
    _tree_frame,
)
from scraper.database import Database
from scraper.recentlybooked import RecentlyBookedScraper
from scraper.searcher import ArrestSearcher, _is_compatible, format_race_label

_RB_COLS = ["name", "race", "state", "county", "charge", "hint"]
_RB_WIDTHS = [180, 80, 50, 100, 200, 140]


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

    def _rb_hint(self, record: Dict[str, Any], eth=None) -> str:
        if eth is None:
            eth = ArrestSearcher(self.db_path).ethnic_db
        n = self._rb_name(record)
        last = (record.get("last_name") or "").strip()
        if not last and n:
            last = n.split()[-1]
        first = (record.get("first_name") or "").strip() or None
        likely, conf, _ = eth.classify_by_name(last, first_name=first)
        race = record.get("race") or ""
        hint = f"{likely} {conf:.0%}"
        if (
            likely != "Unknown"
            and race
            and not _is_compatible(likely, race, record.get("ethnicity"))
        ):
            hint = f"FLAG {hint} vs {format_race_label(race)}"
        return hint

    @staticmethod
    def _rb_name(record: Dict[str, Any]) -> str:
        return (
            record.get("full_name")
            or f"{record.get('first_name') or ''} {record.get('last_name') or ''}".strip()
            or "—"
        )

    def _rb_row_values(self, record: Dict[str, Any], eth=None) -> tuple:
        return (
            self._rb_name(record),
            record.get("race") or "",
            record.get("state") or "",
            record.get("county") or "",
            (record.get("charge_description") or "")[:40],
            self._rb_hint(record, eth),
        )

    def _rb_persist_verdict(self, record: Dict[str, Any], verdict: str) -> bool:
        """Write ethnicity_review into flags; resolve id via source_url when needed."""
        flags_json = merge_ethnicity_review_flags(record.get("flags"), verdict)
        record["flags"] = flags_json
        rid = record.get("id")
        source_url = str(record.get("source_url") or "").strip()
        db = Database(self.db_path)
        try:
            if rid is None and source_url:
                row = db._conn.execute(
                    "SELECT id, flags FROM arrests WHERE source_url = ? LIMIT 1",
                    (source_url,),
                ).fetchone()
                if row:
                    rid = row["id"] if hasattr(row, "keys") else row[0]
                    existing = row["flags"] if hasattr(row, "keys") else row[1]
                    flags_json = merge_ethnicity_review_flags(existing, verdict)
                    record["flags"] = flags_json
            if rid is None:
                return False
            record["id"] = int(rid)
            return bool(db.update_arrest(int(rid), {"flags": flags_json}))
        finally:
            db.close()

    def _rb_apply_verdict(
        self,
        record: Dict[str, Any],
        verdict: str,
        *,
        tree,
        records: List[Dict[str, Any]],
        sidebar: RecordSidebar,
        remove_from_list: bool = False,
    ) -> None:
        label = (
            "classified correctly"
            if verdict == "correct"
            else "classified incorrectly"
        )
        saved = self._rb_persist_verdict(record, verdict)
        # Keep in-memory copy in sync for the current selection index.
        for i, existing in enumerate(records):
            same_id = record.get("id") and existing.get("id") == record.get("id")
            same_url = (
                record.get("source_url")
                and existing.get("source_url") == record.get("source_url")
            )
            if same_id or same_url or existing is record:
                existing["flags"] = record.get("flags")
                if record.get("id") is not None:
                    existing["id"] = record["id"]
                idx = i
                break
        else:
            idx = None

        if saved:
            self.log(f"Marked {self._rb_name(record)} as {label}.")
        else:
            self.log(
                f"Marked {self._rb_name(record)} as {label} "
                "(not in DB yet — import to persist)."
            )

        if remove_from_list and idx is not None:
            children = tree.get_children()
            if 0 <= idx < len(children):
                tree.delete(children[idx])
            records.pop(idx)
            if records:
                next_i = min(idx, len(records) - 1)
                kids = tree.get_children()
                if kids:
                    tree.selection_set(kids[next_i])
                    tree.focus(kids[next_i])
                    tree.see(kids[next_i])
                    sidebar.show(records[next_i])
                else:
                    sidebar.clear()
            else:
                sidebar.clear("No more rows.")
            return

        sidebar.show(record)

    def _rb_split(
        self, parent, *, records_attr: str, tree_attr: str, sidebar_attr: str,
        remove_on_verdict: bool = False,
    ):
        """Tree on the left, photo/details sidebar on the right."""
        pane = _hpaned(parent)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        tree.configure(columns=_RB_COLS)
        _enable_tree_column_sort(tree, _RB_COLS)
        _stretch_columns(tree, _RB_COLS, _RB_WIDTHS)
        sidebar = RecordSidebar(pane)
        sidebar.bind_after(self.after)
        sidebar.bind_verdict(
            lambda rec, verdict: self._rb_apply_verdict(
                rec,
                verdict,
                tree=tree,
                records=getattr(self, records_attr),
                sidebar=sidebar,
                remove_from_list=remove_on_verdict,
            )
        )
        pane.add(left, minsize=360, stretch="always")
        pane.add(sidebar.frame, minsize=280, stretch="never")
        setattr(self, records_attr, [])
        setattr(self, tree_attr, tree)
        setattr(self, sidebar_attr, sidebar)

        def on_select(_event=None):
            records: List[Dict[str, Any]] = getattr(self, records_attr)
            sel = tree.selection()
            if not sel:
                sidebar.clear()
                return
            try:
                idx = tree.index(sel[0])
            except Exception:
                return
            if 0 <= idx < len(records):
                sidebar.show(records[idx])

        tree.bind("<<TreeviewSelect>>", on_select)
        return tree, sidebar

    def _rb_append_row(
        self,
        tree,
        records: List[Dict[str, Any]],
        record: Dict[str, Any],
        *,
        eth=None,
        sidebar: Optional[RecordSidebar] = None,
        select_latest: bool = False,
        status_label=None,
        status_fmt: str = "{n} records",
    ) -> None:
        records.append(record)
        item = tree.insert("", "end", values=self._rb_row_values(record, eth))
        if status_label is not None:
            status_label.configure(text=status_fmt.format(n=len(records)))
        if select_latest:
            tree.selection_set(item)
            tree.see(item)
            if sidebar is not None:
                sidebar.show(record)

    # ── Live Feed ───────────────────────────────────────────────────────

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
        self.rb_live_status = ctk.CTkLabel(
            bar,
            text="Homepage bookings — Refresh streams cards into the list.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.rb_live_status.pack(side="left", padx=12)
        self._rb_split(
            tab,
            records_attr="_rb_records",
            tree_attr="rb_tree",
            sidebar_attr="rb_live_sidebar",
        )

    def _rb_refresh(self):
        self.log("Live feed: fetching homepage…")
        self.rb_live_status.configure(text="Refreshing…")
        self._rb_records = []
        self.rb_tree.delete(*self.rb_tree.get_children())
        self.rb_live_sidebar.clear("Loading…")

        def work():
            try:
                eth = ArrestSearcher(self.db_path).ethnic_db
                delay = float(self.app_settings.get("rb_delay") or 1.0)

                def on_record(rec: Dict[str, Any], n: int) -> None:
                    row = dict(rec)

                    def ui() -> None:
                        self._rb_append_row(
                            self.rb_tree,
                            self._rb_records,
                            row,
                            eth=eth,
                            sidebar=self.rb_live_sidebar,
                            select_latest=(n == 1),
                            status_label=self.rb_live_status,
                            status_fmt="Live feed: {n} loaded…",
                        )
                        if n == 1 or n % 5 == 0:
                            self.log(f"Live feed: {n} loaded…")

                    self.after(0, ui)

                with RecentlyBookedScraper(delay=delay) as s:
                    rows = s.scrape_live(
                        import_details=True,
                        with_photos=False,
                        with_html=False,
                        record_cb=on_record,
                    )
                self.after(
                    0,
                    lambda: self.rb_live_status.configure(
                        text=f"Live feed: {len(rows)} records."
                    ),
                )
                self.log(f"Live feed: {len(rows)} records.")
            except Exception as e:
                self.log(f"Live feed failed: {e}")
                self.after(
                    0,
                    lambda: self.rb_live_status.configure(text=f"Failed: {e}"),
                )

        threading.Thread(target=work, daemon=True).start()

    def _rb_import(self, all_rows: bool):
        if not self._rb_records:
            self.log("No live-feed rows to import.")
            return
        if all_rows:
            rows = list(self._rb_records)
        else:
            indexes = [self.rb_tree.index(i) for i in self.rb_tree.selection()]
            rows = [
                self._rb_records[i]
                for i in indexes
                if 0 <= i < len(self._rb_records)
            ]
        if not rows:
            self.log("No live-feed rows selected.")
            return

        with_photos = bool(self.app_settings.get("rb_with_photos", True))
        with_html = bool(self.app_settings.get("rb_with_html", True))
        delay = float(self.app_settings.get("rb_delay") or 1.0)
        need_archive = (with_photos or with_html) and any(
            (with_photos and not r.get("photo_path"))
            or (with_html and not r.get("html_path"))
            for r in rows
        )

        def work():
            try:
                to_import = rows
                if need_archive:
                    self.log(
                        f"Live feed import: archiving {len(rows)} "
                        f"(photos={with_photos}, html={with_html})…"
                    )
                    with RecentlyBookedScraper(delay=delay) as s:
                        to_import = [
                            s._process_record(
                                dict(r),
                                import_details=False,
                                with_photos=with_photos,
                                with_html=with_html,
                            )
                            for r in rows
                        ]
                db = Database(self.db_path)
                try:
                    result = db.import_records(to_import, skip_existing_urls=True)
                finally:
                    db.close()
                self.log(
                    f"RecentlyBooked import: +{result['imported']}, "
                    f"{result['skipped']} skipped."
                )
                self.after(0, self._refresh_db_status)
            except Exception as e:
                self.log(f"Live feed import failed: {e}")

        threading.Thread(target=work, daemon=True).start()

    # ── Misclassify ─────────────────────────────────────────────────────

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
        self.rb_mc_status = ctk.CTkLabel(
            bar,
            text="Select a flag for photo/details and Open source URL.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.rb_mc_status.pack(side="left", padx=12)

        pane = _hpaned(tab)
        pane.pack(fill="both", expand=True, padx=8, pady=8)
        left = ctk.CTkFrame(pane, fg_color="transparent")
        wrap, self.rb_mc_tree = _tree_frame(left)
        wrap.pack(fill="both", expand=True)
        cols = ["name", "race", "likely", "conf", "charge", "state"]
        self.rb_mc_tree.configure(columns=cols)
        _enable_tree_column_sort(self.rb_mc_tree, cols)
        _stretch_columns(self.rb_mc_tree, cols, [180, 90, 100, 60, 180, 50])
        self.rb_mc_sidebar = RecordSidebar(pane)
        self.rb_mc_sidebar.bind_after(self.after)
        self.rb_mc_sidebar.bind_verdict(
            lambda rec, verdict: self._rb_apply_verdict(
                rec,
                verdict,
                tree=self.rb_mc_tree,
                records=self._rb_mc_records,
                sidebar=self.rb_mc_sidebar,
                remove_from_list=True,
            )
        )
        pane.add(left, minsize=360, stretch="always")
        pane.add(self.rb_mc_sidebar.frame, minsize=280, stretch="never")
        self._rb_mc_records: List[Dict[str, Any]] = []

        def on_select(_event=None):
            sel = self.rb_mc_tree.selection()
            if not sel:
                self.rb_mc_sidebar.clear()
                return
            try:
                idx = self.rb_mc_tree.index(sel[0])
            except Exception:
                return
            if 0 <= idx < len(self._rb_mc_records):
                self.rb_mc_sidebar.show(self._rb_mc_records[idx])

        self.rb_mc_tree.bind("<<TreeviewSelect>>", on_select)

    def _rb_analyze(self):
        self.rb_mc_status.configure(text="Analyzing…")
        self.rb_mc_sidebar.clear("Analyzing…")

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
                self._rb_mc_records = []
                for mc in rows:
                    rec = dict(mc.record or {})
                    # Keep analysis fields available in the sidebar text.
                    rec.setdefault("race", mc.expected_race)
                    if mc.likely_ethnicity:
                        rec["likely_ethnicity"] = mc.likely_ethnicity
                    if mc.confidence is not None:
                        rec["confidence"] = mc.confidence
                    self._rb_mc_records.append(rec)
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
                msg = (
                    f"RecentlyBooked surname analysis: "
                    f"{len(rows)} flags from {base} names."
                )
                self.log(msg)
                self.rb_mc_status.configure(text=msg)
                if self._rb_mc_records:
                    first = self.rb_mc_tree.get_children()
                    if first:
                        self.rb_mc_tree.selection_set(first[0])
                        self.rb_mc_tree.focus(first[0])
                        self.rb_mc_sidebar.show(self._rb_mc_records[0])
                else:
                    self.rb_mc_sidebar.clear("No flags.")

            self.after(0, fill)

        threading.Thread(target=work, daemon=True).start()

    # ── Full Scrape ─────────────────────────────────────────────────────

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
        self.rb_full_status = ctk.CTkLabel(
            bar,
            text="Records stream in live; select a row for photo/details.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.rb_full_status.pack(side="left", padx=12)
        self._rb_split(
            tab,
            records_attr="_rb_full_records",
            tree_attr="rb_full_tree",
            sidebar_attr="rb_full_sidebar",
        )

    def _rb_full_start(self):
        self.rb_cancel = False
        state = self.rb_state.get().strip()
        county = self.rb_county.get().strip()
        scrape_all = bool(self.rb_all.get())
        if not scrape_all and not state:
            self.log("Enter a state or enable All states.")
            return

        db_path = self.db_path
        delay = float(self.app_settings.get("rb_delay") or 1.0)
        with_photos = bool(self.app_settings.get("rb_with_photos", True))
        with_html = bool(self.app_settings.get("rb_with_html", True))

        self._rb_full_records = []
        self.rb_full_tree.delete(*self.rb_full_tree.get_children())
        self.rb_full_sidebar.clear("Scraping…")
        self.rb_full_status.configure(text="Starting…")
        self.log("RecentlyBooked full scrape started…")

        def work():
            imported = 0
            skipped = 0
            shown = [0]
            try:
                eth = ArrestSearcher(db_path).ethnic_db
                db = Database(db_path)
                try:
                    known = db.existing_source_urls()

                    def on_record(rec: Dict[str, Any], n: int) -> None:
                        nonlocal imported, skipped
                        row = dict(rec)
                        try:
                            result = db.import_records(
                                [row], skip_existing_urls=True
                            )
                            imported += int(result.get("imported") or 0)
                            skipped += int(result.get("skipped") or 0)
                            url = str(row.get("source_url") or "")
                            if url:
                                known.add(url)
                        except Exception as exc:
                            row["scrape_error"] = (
                                row.get("scrape_error") or f"import: {exc}"
                            )

                        def ui() -> None:
                            self._rb_append_row(
                                self.rb_full_tree,
                                self._rb_full_records,
                                row,
                                eth=eth,
                                sidebar=self.rb_full_sidebar,
                                select_latest=(n == 1),
                                status_label=self.rb_full_status,
                                status_fmt=(
                                    f"{{n}} shown · +{imported} imported · "
                                    f"{skipped} skipped"
                                ),
                            )
                            if n == 1 or n % 10 == 0:
                                self.log(
                                    f"RecentlyBooked: {n} records "
                                    f"(+{imported} imported)"
                                )

                        self.after(0, ui)
                        shown[0] = n

                    with RecentlyBookedScraper(delay=delay) as s:
                        kw = dict(
                            with_photos=with_photos,
                            with_html=with_html,
                            skip_existing_urls=known,
                            cancel_check=lambda: self.rb_cancel,
                            record_cb=on_record,
                        )
                        if scrape_all:
                            s.scrape_all(**kw)
                        elif county:
                            s.scrape_county(state, county, **kw)
                        else:
                            s.scrape_state(state, **kw)
                finally:
                    db.close()

                msg = (
                    f"RecentlyBooked full scrape done: "
                    f"{shown[0]} shown, "
                    f"+{imported} imported, {skipped} skipped."
                )
                self.log(msg)
                self.after(0, lambda: self.rb_full_status.configure(text=msg))
                self.after(0, self._refresh_db_status)
            except Exception as e:
                self.log(f"RecentlyBooked scrape failed: {e}")
                self.after(
                    0,
                    lambda: self.rb_full_status.configure(text=f"Failed: {e}"),
                )

        threading.Thread(target=work, daemon=True).start()
