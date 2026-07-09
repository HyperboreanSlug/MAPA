#!/usr/bin/env python3
"""
Arrest Public Archiver GUI

Primary purpose: find ethnic surname vs recorded-race misclassifications
in publicly published arrest/booking open data.
"""

from __future__ import annotations

import queueing
import threading
from pathlib import Path
from typing import Any, Dict, Optional

import customtkinter as ctk
from tkinter import filedialog, messagebox, ttk

from scraper.app_settings import DEFAULTS, load_settings, save_settings
from scraper.charge_classifications import (
    category_label,
    list_category_choices,
)
from scraper.config import SOURCES, get_bulk_sources, get_named_sources
from scraper.database import Database
from scraper.searcher import ArrestSearcher
from scraper.scrapers.base import ScraperFactory

C = {
    "bg": "#0f1115",
    "surface": "#161a22",
    "panel": "#1c2230",
    "elevated": "#252b3a",
    "border": "#2e3648",
    "text": "#e8eaef",
    "muted": "#9aa3b5",
    "dim": "#6b7385",
    "accent": "#5b8def",
    "accent_hover": "#4a7ad4",
}
FONT = ("Segoe UI", 13)
FONT_SM = ("Segoe UI", 12)
FONT_BOLD = ("Segoe UI", 13, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")


class ArrestArchiverApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("Arrest Public Archiver — Ethnic Misclassification")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=C["bg"])

        self.app_settings = load_settings()
        self.db_path = self.app_settings.get("db_path") or DEFAULTS["db_path"]
        self.log_queue: queue.Queue = queue.Queue()
        self.is_running = False

        header = ctk.CTkFrame(self, fg_color=C["surface"], height=52, corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(
            header,
            text="Arrest Public Archiver",
            font=FONT_TITLE,
            text_color=C["text"],
        ).pack(side="left", padx=16, pady=10)
        ctk.CTkLabel(
            header,
            text="Primary: ethnic misclassification of public arrest/booking records",
            font=FONT_SM,
            text_color=C["muted"],
        ).pack(side="left", padx=8)
        self.header_db = ctk.CTkLabel(header, text="", font=FONT_SM, text_color=C["dim"])
        self.header_db.pack(side="right", padx=16)

        self.tabs = ctk.CTkTabview(
            self,
            fg_color=C["bg"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent"],
            segmented_button_selected_hover_color=C["accent_hover"],
            segmented_button_unselected_color=C["panel"],
            text_color=C["text"],
        )
        self.tabs.pack(fill="both", expand=True, padx=10, pady=10)
        # Misclassify first — primary purpose
        for name in ("Misclassify", "Scrape", "Search", "Integrity", "Settings"):
            self.tabs.add(name)

        self._build_misclassify(self.tabs.tab("Misclassify"))
        self._build_scrape(self.tabs.tab("Scrape"))
        self._build_search(self.tabs.tab("Search"))
        self._build_integrity(self.tabs.tab("Integrity"))
        self._build_settings(self.tabs.tab("Settings"))

        log_fr = ctk.CTkFrame(self, fg_color=C["surface"], height=100, corner_radius=0)
        log_fr.pack(fill="x")
        self.log_box = ctk.CTkTextbox(
            log_fr, height=90, fg_color=C["panel"], text_color=C["muted"], font=("Consolas", 11)
        )
        self.log_box.pack(fill="x", padx=8, pady=6)
        self._refresh_header()
        self.after(200, self._poll_log)
        self.log("Ready. Prefer sources with names (Scrape → Named only) then Misclassify → Analyze.")

    def log(self, msg: str) -> None:
        self.log_queue.put(msg)

    def _poll_log(self) -> None:
        try:
            while True:
                msg = self.log_queue.get_nowait()
                self.log_box.insert("end", msg + "\n")
                self.log_box.see("end")
        except queue.Empty:
            pass
        self.after(200, self._poll_log)

    def _refresh_header(self) -> None:
        try:
            db = Database(self.db_path)
            try:
                n = db.get_total_count()
            finally:
                db.close()
            self.header_db.configure(text=f"DB: {self.db_path}  ·  {n:,} records")
        except Exception:
            self.header_db.configure(text=f"DB: {self.db_path}")

    # ----- Misclassify (PRIMARY) -----
    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=12)
        ctk.CTkLabel(bar, text="Ethnicity", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(0, 6)
        )
        self.mc_eth = ctk.StringVar(value="all")
        ctk.CTkComboBox(
            bar,
            variable=self.mc_eth,
            width=160,
            values=[
                "all", "hispanic", "asian", "indian", "indian_high_confidence",
                "african_american", "arabic", "jewish", "portuguese",
                "native_american", "european",
            ],
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(bar, text="Charge", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(0, 6)
        )
        self.mc_charge = ctk.StringVar(value="all")
        ctk.CTkComboBox(
            bar,
            variable=self.mc_charge,
            width=150,
            values=list_category_choices(include_all=True),
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
        ).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(bar, text="Min conf.", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(0, 4)
        )
        self.mc_conf = ctk.DoubleVar(value=0.5)
        ctk.CTkEntry(bar, textvariable=self.mc_conf, width=56, fg_color=C["bg"],
                     border_color=C["border"], text_color=C["text"]).pack(side="left")
        ctk.CTkButton(
            bar, text="Analyze misclassifications", width=200,
            command=self._run_misclass,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(side="left", padx=12)
        ctk.CTkButton(
            bar, text="Export CSV", width=100, command=self._export_misclass,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left")

        ctk.CTkLabel(
            tab,
            text=(
                "Compares surname ethnicity lists to the race field on each arrest row. "
                "Filter by charge category (sex_crimes, burglary_be, drugs, …). "
                "Only records with names are scored."
            ),
            font=FONT_SM, text_color=C["dim"], wraplength=980, justify="left",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        self.mc_status = ctk.CTkLabel(tab, text="Run Analyze to scan.", font=FONT_SM, text_color=C["muted"])
        self.mc_status.pack(anchor="w", padx=14)

        tree_fr = ctk.CTkFrame(tab, fg_color=C["panel"])
        tree_fr.pack(fill="both", expand=True, padx=12, pady=10)
        cols = ("name", "race", "likely", "conf", "category", "charge", "state")
        self.mc_tree = ttk.Treeview(tree_fr, columns=cols, show="headings", height=18)
        for c, t, w in (
            ("name", "Name", 140), ("race", "Recorded race", 100),
            ("likely", "Likely ethnicity", 130), ("conf", "Conf", 55),
            ("category", "Charge cat.", 110), ("charge", "Charge", 200),
            ("state", "ST", 40),
        ):
            self.mc_tree.heading(c, text=t)
            self.mc_tree.column(c, width=w, anchor="w")
        sb = ttk.Scrollbar(tree_fr, orient="vertical", command=self.mc_tree.yview)
        self.mc_tree.configure(yscrollcommand=sb.set)
        self.mc_tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self._mc_results = []

    def _run_misclass(self) -> None:
        eth = self.mc_eth.get()
        eth_f = None if eth == "all" else eth
        ch = self.mc_charge.get()
        ch_f = None if ch == "all" else ch
        try:
            conf = float(self.mc_conf.get())
        except (TypeError, ValueError):
            conf = 0.5
        searcher = ArrestSearcher(self.db_path)
        try:
            results, base = searcher.analyze_ethnicities(
                min_confidence=conf,
                limit=0,
                ethnicity_filter=eth_f,
                charge_category=ch_f,
                return_base_count=True,
                named_only=True,
            )
            total = searcher.get_total_count()
        finally:
            searcher.close()
        self._mc_results = results
        self.mc_tree.delete(*self.mc_tree.get_children())
        for mc in results[:500]:
            rec = mc.record or {}
            name = (
                f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
            ).strip() or rec.get("full_name") or "—"
            cat = rec.get("charge_category") or ""
            self.mc_tree.insert(
                "", "end",
                values=(
                    name,
                    mc.expected_race,
                    mc.likely_ethnicity,
                    f"{mc.confidence:.3f}",
                    category_label(cat) if cat else "—",
                    (rec.get("charge_description") or "")[:55],
                    rec.get("state") or "",
                ),
            )
        rate = (len(results) / base * 100.0) if base else 0.0
        self.mc_status.configure(
            text=(
                f"DB {total:,} rows · named matches {base:,} · "
                f"misclassified {len(results):,} ({rate:.1f}%)"
                + (f" · charge={ch}" if ch_f else "")
            )
        )
        self.log(
            f"Misclass: {len(results)} / base {base} (eth={eth}, charge={ch}, conf>={conf})"
        )

    def _export_misclass(self) -> None:
        path = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV", "*.csv")]
        )
        if not path:
            return
        eth = self.mc_eth.get()
        eth_f = None if eth == "all" else eth
        ch = self.mc_charge.get()
        ch_f = None if ch == "all" else ch
        searcher = ArrestSearcher(self.db_path)
        try:
            n = searcher.export_misclassifications(
                path,
                ethnicity_filter=eth_f,
                charge_category=ch_f,
                min_confidence=float(self.mc_conf.get()),
            )
        finally:
            searcher.close()
        self.log(f"Exported {n} misclass rows → {path}")
        messagebox.showinfo("Export", f"Exported {n} rows.")

    # ----- Scrape -----
    def _build_scrape(self, tab):
        tab.configure(fg_color=C["surface"])
        ctk.CTkLabel(
            tab,
            text="Download public open-data arrest/booking feeds. Prefer Named sources for misclassification.",
            font=FONT_SM, text_color=C["muted"],
        ).pack(anchor="w", padx=14, pady=(12, 6))

        self.scrape_named_only = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            tab, text="Named sources only (recommended for misclassification)",
            variable=self.scrape_named_only, font=FONT_SM, text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            checkmark_color=C["bg"], border_color=C["border"],
        ).pack(anchor="w", padx=14, pady=4)
        self.scrape_auto_import = ctk.BooleanVar(
            value=bool(self.app_settings.get("scrape_auto_import", True))
        )
        ctk.CTkCheckBox(
            tab, text="Import into DB after download",
            variable=self.scrape_auto_import, font=FONT_SM, text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            checkmark_color=C["bg"], border_color=C["border"],
        ).pack(anchor="w", padx=14, pady=4)

        row = ctk.CTkFrame(tab, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=8)
        ctk.CTkLabel(row, text="Row limit (0=source default)", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(0, 6)
        )
        self.scrape_limit = ctk.IntVar(
            value=int(self.app_settings.get("scrape_default_row_limit", 5000))
        )
        ctk.CTkEntry(row, textvariable=self.scrape_limit, width=80, fg_color=C["bg"],
                     border_color=C["border"], text_color=C["text"]).pack(side="left")
        ctk.CTkButton(
            row, text="Scrape selected / named", command=self._start_scrape,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(side="left", padx=16)

        # Source list
        tree_fr = ctk.CTkFrame(tab, fg_color=C["panel"])
        tree_fr.pack(fill="both", expand=True, padx=12, pady=10)
        cols = ("id", "name", "state", "method", "names", "status")
        self.src_tree = ttk.Treeview(tree_fr, columns=cols, show="headings", height=14, selectmode="extended")
        for c, t, w in (
            ("id", "ID", 140), ("name", "Name", 260), ("state", "ST", 40),
            ("method", "Method", 80), ("names", "Names", 50), ("status", "Status", 100),
        ):
            self.src_tree.heading(c, text=t)
            self.src_tree.column(c, width=w)
        self.src_tree.pack(fill="both", expand=True, padx=4, pady=4)
        for s in SOURCES:
            self.src_tree.insert(
                "", "end",
                values=(s.id, s.name, s.state, s.scrape_method,
                        "yes" if s.has_names else "no", s.status),
            )

    def _start_scrape(self) -> None:
        if self.is_running:
            return
        sel = self.src_tree.selection()
        if sel:
            ids = [self.src_tree.item(i, "values")[0] for i in sel]
        elif self.scrape_named_only.get():
            ids = [s.id for s in get_named_sources()]
        else:
            ids = [s.id for s in get_bulk_sources()]
        if not ids:
            messagebox.showwarning("No sources", "Select sources or enable named-only.")
            return
        try:
            limit = int(self.scrape_limit.get())
        except (TypeError, ValueError):
            limit = 5000
        auto_imp = bool(self.scrape_auto_import.get())
        db_path = self.db_path
        self.is_running = True

        def worker():
            try:
                for sid in ids:
                    self.log(f"Scraping {sid}…")
                    try:
                        scraper = ScraperFactory.create(sid, delay=1.0)
                        try:
                            out = Path("data/downloads")
                            path = scraper.scrape_to_file(out, row_limit=limit)
                            recs = scraper.scrape(row_limit=limit)
                            self.log(f"  {sid}: {len(recs)} rows → {path}")
                            if auto_imp and recs:
                                db = Database(db_path)
                                try:
                                    r = db.import_records(recs, skip_existing_urls=True)
                                    self.log(
                                        f"  DB +{r['imported']} (skip {r['skipped']})"
                                    )
                                finally:
                                    db.close()
                        finally:
                            scraper.close()
                    except Exception as e:
                        self.log(f"  ERROR {sid}: {e}")
                self.log("Scrape done. Run Misclassify → Analyze.")
            finally:
                self.is_running = False
                self.after(0, self._refresh_header)

        threading.Thread(target=worker, daemon=True).start()

    # ----- Search -----
    def _build_search(self, tab):
        tab.configure(fg_color=C["surface"])
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=12)
        self.search_name = ctk.StringVar()
        ctk.CTkEntry(
            bar, textvariable=self.search_name, width=180, placeholder_text="Name (optional)",
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(bar, text="Charge", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(0, 4)
        )
        self.search_charge = ctk.StringVar(value="all")
        ctk.CTkComboBox(
            bar,
            variable=self.search_charge,
            width=150,
            values=list_category_choices(include_all=True),
            fg_color=C["bg"], border_color=C["border"], button_color=C["elevated"],
            text_color=C["text"], dropdown_fg_color=C["panel"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            bar, text="Search", width=100, command=self._run_search,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(side="left")
        tree_fr = ctk.CTkFrame(tab, fg_color=C["panel"])
        tree_fr.pack(fill="both", expand=True, padx=12, pady=10)
        cols = ("name", "race", "category", "charge", "state", "date")
        self.search_tree = ttk.Treeview(tree_fr, columns=cols, show="headings")
        for c, t, w in (
            ("name", "Name", 140), ("race", "Race", 90), ("category", "Category", 120),
            ("charge", "Charge", 240), ("state", "ST", 40), ("date", "Date", 100),
        ):
            self.search_tree.heading(c, text=t)
            self.search_tree.column(c, width=w)
        self.search_tree.pack(fill="both", expand=True)

    def _run_search(self) -> None:
        name = (self.search_name.get() or "").strip()
        ch = self.search_charge.get()
        ch_f = None if ch == "all" else ch
        if not name and not ch_f:
            messagebox.showinfo("Search", "Enter a name and/or pick a charge category.")
            return
        s = ArrestSearcher(self.db_path)
        try:
            res = s.search(name=name or None, charge_category=ch_f, limit=300)
        finally:
            s.close()
        self.search_tree.delete(*self.search_tree.get_children())
        for r in res.records:
            nm = (
                f"{r.get('first_name') or ''} {r.get('last_name') or ''}"
            ).strip() or r.get("full_name") or "—"
            cat = r.get("charge_category") or ""
            self.search_tree.insert(
                "", "end",
                values=(
                    nm, r.get("race") or "",
                    category_label(cat) if cat else "—",
                    (r.get("charge_description") or "")[:80],
                    r.get("state") or "",
                    r.get("arrest_date") or r.get("booking_date") or "",
                ),
            )
        self.log(f"Search name={name!r} charge={ch}: {len(res.records)} hits")

    # ----- Integrity -----
    def _build_integrity(self, tab):
        tab.configure(fg_color=C["surface"])
        bar = ctk.CTkFrame(tab, fg_color="transparent")
        bar.pack(fill="x", padx=12, pady=12)
        ctk.CTkButton(
            bar, text="Refresh", command=self._refresh_integrity,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(side="left")
        ctk.CTkButton(
            bar, text="Remove URL duplicates", command=self._dedupe,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=8)
        self.integrity_label = ctk.CTkLabel(
            tab, text="Click Refresh.", font=FONT_SM, text_color=C["text"], justify="left"
        )
        self.integrity_label.pack(anchor="w", padx=14, pady=8)

    def _refresh_integrity(self) -> None:
        db = Database(self.db_path)
        try:
            rep = db.get_integrity_report()
            dups = db.find_duplicate_groups("source_url")
        finally:
            db.close()
        o = rep["overall"]
        extra = sum(g["count"] - 1 for g in dups)
        charge_lines = ""
        try:
            db2 = Database(self.db_path)
            try:
                cats = db2.get_charge_category_distribution()
            finally:
                db2.close()
            top = cats[:8]
            if top:
                charge_lines = "\nCharge categories: " + ", ".join(
                    f"{c['label']} {c['count']:,}" for c in top
                )
        except Exception:
            pass
        self.integrity_label.configure(
            text=(
                f"Total: {o['total']:,}\n"
                f"With name: {o['with_name']:,} ({o.get('pct_name', 0)}%)  ← required for misclass\n"
                f"With race: {o['with_race']:,} ({o.get('pct_race', 0)}%)\n"
                f"With charge: {o['with_charge']:,} ({o.get('pct_charge', 0)}%)\n"
                f"Duplicate source_url extra rows: {extra:,}"
                f"{charge_lines}"
            )
        )
        self._refresh_header()

    def _dedupe(self) -> None:
        db = Database(self.db_path)
        try:
            preview = db.remove_duplicates("source_url", dry_run=True)
            if preview["deleted"] <= 0:
                messagebox.showinfo("Dedupe", "No duplicates.")
                return
            if not messagebox.askyesno("Dedupe", f"Delete {preview['deleted']} duplicate rows?"):
                return
            r = db.remove_duplicates("source_url", dry_run=False)
        finally:
            db.close()
        self.log(f"Dedupe deleted {r['deleted']}")
        self._refresh_integrity()

    # ----- Settings -----
    def _build_settings(self, tab):
        tab.configure(fg_color=C["surface"])
        ctk.CTkLabel(tab, text="Database path", font=FONT_SM, text_color=C["muted"]).pack(
            anchor="w", padx=14, pady=(16, 4)
        )
        self.settings_db = ctk.StringVar(value=self.db_path)
        ctk.CTkEntry(
            tab, textvariable=self.settings_db, width=480,
            fg_color=C["bg"], border_color=C["border"], text_color=C["text"],
        ).pack(anchor="w", padx=14)
        ctk.CTkButton(
            tab, text="Save settings", command=self._save_settings,
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        ).pack(anchor="w", padx=14, pady=16)
        ctk.CTkLabel(
            tab,
            text=(
                "Arrest ≠ conviction. Only use published open data. "
                "Respect portal terms and rate limits. Data may be incomplete or sealed."
            ),
            font=FONT_SM, text_color=C["dim"], wraplength=800, justify="left",
        ).pack(anchor="w", padx=14, pady=8)

    def _save_settings(self) -> None:
        self.db_path = self.settings_db.get().strip() or DEFAULTS["db_path"]
        self.app_settings["db_path"] = self.db_path
        self.app_settings["scrape_auto_import"] = bool(self.scrape_auto_import.get())
        save_settings(self.app_settings)
        self.log(f"Settings saved. DB={self.db_path}")
        self._refresh_header()


def main():
    app = ArrestArchiverApp()
    app.mainloop()


if __name__ == "__main__":
    main()
