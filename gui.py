#!/usr/bin/env python3
"""
Arrest Public Archiver GUI

Primary purpose: find ethnic surname vs recorded-race misclassifications
in publicly published arrest/booking open data.
"""

from __future__ import annotations

import queue
import re
import threading
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _setup_dark_treeview() -> None:
    style = ttk.Style()
    try:
        style.theme_use("clam")
    except Exception:
        pass
    style.configure(
        "Dark.Treeview",
        background=C["panel"],
        fieldbackground=C["panel"],
        foreground=C["text"],
        borderwidth=0,
        rowheight=24,
    )
    style.configure(
        "Dark.Treeview.Heading",
        background=C["elevated"],
        foreground=C["muted"],
        relief="flat",
    )
    style.map("Dark.Treeview", background=[("selected", C["accent"])])


def _misclass_race_bucket(recorded_race: Optional[str]) -> str:
    """Parity with SOR Statistics: Black / White / Other only."""
    key = (recorded_race or "").strip().upper()
    if key in ("WHITE", "W", "CAUCASIAN", "CAUCASION"):
        return "White"
    if key in (
        "BLACK", "B", "AFRICAN AMERICAN", "AFRICAN-AMERICAN",
        "BLACK OR AFRICAN AMERICAN",
    ):
        return "Black"
    return "Other"


def _tree_cell_sort_key(val: Any):
    s = str(val if val is not None else "").strip()
    if not s or s in ("—", "–", "-", "N/A", "n/a", "None"):
        return (2, 0.0, "")
    cleaned = s.replace(",", "").replace("\u00a0", " ").strip()
    if cleaned.endswith("%"):
        cleaned = cleaned[:-1].strip()
    try:
        return (0, float(cleaned), "")
    except ValueError:
        pass
    m = re.match(r"^([+-]?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)", cleaned)
    if m:
        try:
            return (0, float(m.group(1)), s.casefold())
        except ValueError:
            pass
    return (1, 0.0, s.casefold())


def _enable_tree_column_sort(
    tree: ttk.Treeview,
    columns: List[str],
    labels: Optional[Dict[str, str]] = None,
) -> None:
    labels = labels or {c: c.upper() for c in columns}
    state: Dict[str, Any] = {"col": None, "reverse": False}

    def apply_sort(col: str, reverse: bool, update_headings: bool = True) -> None:
        rows = [(tree.set(iid, col), iid) for iid in tree.get_children("")]
        rows.sort(key=lambda t: _tree_cell_sort_key(t[0]), reverse=reverse)
        for idx, (_val, iid) in enumerate(rows):
            tree.move(iid, "", idx)
        state["col"] = col
        state["reverse"] = reverse
        if update_headings:
            for c in columns:
                base = labels.get(c, c.upper())
                if c == col:
                    arrow = " ▼" if reverse else " ▲"
                    tree.heading(
                        c, text=base + arrow, command=lambda cc=c: on_heading(cc)
                    )
                else:
                    tree.heading(c, text=base, command=lambda cc=c: on_heading(cc))

    def on_heading(col: str) -> None:
        reverse = state["col"] == col and not state["reverse"]
        apply_sort(col, reverse)

    for c in columns:
        tree.heading(
            c, text=labels.get(c, c.upper()), command=lambda cc=c: on_heading(cc)
        )


class ArrestArchiverApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        _setup_dark_treeview()
        self.title("Arrest Public Archiver — Ethnic Misclassification")
        self.geometry("1180x760")
        self.minsize(960, 640)
        self.configure(fg_color=C["bg"])

        self.app_settings = load_settings()
        self.db_path = self.app_settings.get("db_path") or DEFAULTS["db_path"]
        self.log_queue: queue.Queue = queue.Queue()
        self.is_running = False
        self._mc_results = []
        self._mc_meta: Dict[str, Any] = {}

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
        # Misclassify first — primary purpose (parity with SOR Browse layout)
        for name in (
            "Misclassify", "Statistics", "Scrape", "Search", "Integrity", "Settings"
        ):
            self.tabs.add(name)

        self._build_misclassify(self.tabs.tab("Misclassify"))
        self._build_statistics(self.tabs.tab("Statistics"))
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
        self.mc_tree = ttk.Treeview(
            tree_fr, columns=cols, show="headings", height=18, style="Dark.Treeview"
        )
        col_labels = {
            "name": "Name", "race": "Recorded race", "likely": "Likely ethnicity",
            "conf": "Conf", "category": "Charge cat.", "charge": "Charge", "state": "ST",
        }
        for c, w in (
            ("name", 140), ("race", 100), ("likely", 130), ("conf", 55),
            ("category", 110), ("charge", 200), ("state", 40),
        ):
            self.mc_tree.column(c, width=w, anchor="w")
        _enable_tree_column_sort(self.mc_tree, list(cols), labels=col_labels)
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
        self._mc_meta = {
            "db_total": total,
            "eth_base": base,
            "eth_filter": eth,
            "charge_filter": ch,
            "min_conf": conf,
        }
        self.mc_status.configure(
            text=(
                f"DB {total:,} rows · named matches {base:,} · "
                f"misclassified {len(results):,} ({rate:.1f}%)"
                + (f" · charge={ch}" if ch_f else "")
                + " · see Statistics tab"
            )
        )
        self.log(
            f"Misclass: {len(results)} / base {base} (eth={eth}, charge={ch}, conf>={conf})"
        )
        self._update_statistics()

    def _build_statistics(self, tab) -> None:
        """Parity with SOR Statistics: rates + misclassified-as Black/White/Other."""
        tab.configure(fg_color=C["surface"])
        ctk.CTkLabel(
            tab,
            text="Statistics update when you run Analyze on the Misclassify tab.",
            font=FONT_SM, text_color=C["dim"],
        ).pack(anchor="w", padx=14, pady=(12, 6))
        sum_row = ctk.CTkFrame(tab, fg_color="transparent")
        sum_row.pack(fill="x", padx=12, pady=4)
        self.stat_db = ctk.CTkLabel(sum_row, text="DB: —", font=FONT_BOLD, text_color=C["text"])
        self.stat_db.pack(side="left", padx=(0, 16))
        self.stat_base = ctk.CTkLabel(sum_row, text="Ethnicity matches: —", font=FONT_SM, text_color=C["muted"])
        self.stat_base.pack(side="left", padx=(0, 16))
        self.stat_n = ctk.CTkLabel(sum_row, text="Misclassified: —", font=FONT_SM, text_color=C["muted"])
        self.stat_n.pack(side="left", padx=(0, 16))
        self.stat_rate = ctk.CTkLabel(sum_row, text="Rate: —", font=FONT_SM, text_color=C["muted"])
        self.stat_rate.pack(side="left")

        self.stat_filter = ctk.CTkLabel(tab, text="", font=FONT_SM, text_color=C["dim"])
        self.stat_filter.pack(anchor="w", padx=14, pady=(0, 8))

        mid = ctk.CTkFrame(tab, fg_color="transparent")
        mid.pack(fill="both", expand=True, padx=12, pady=6)

        left = ctk.CTkFrame(mid, fg_color=C["panel"])
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))
        ctk.CTkLabel(
            left, text="Misclassified as (race) — Black / White / Other",
            font=FONT_BOLD, text_color=C["text"],
        ).pack(anchor="w", padx=10, pady=(10, 4))
        self.stat_race_summary = ctk.CTkLabel(
            left, text="Run Analyze first.", font=FONT_SM, text_color=C["muted"],
            justify="left",
        )
        self.stat_race_summary.pack(anchor="w", padx=10, pady=(0, 10))

        right = ctk.CTkFrame(mid, fg_color=C["panel"])
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))
        ctk.CTkLabel(
            right, text="By likely ethnicity", font=FONT_BOLD, text_color=C["text"],
        ).pack(anchor="w", padx=10, pady=(10, 4))
        cols = ("eth", "count", "pct")
        self.stat_eth_tree = ttk.Treeview(
            right, columns=cols, show="headings", height=10, style="Dark.Treeview"
        )
        for c, t, w in (("eth", "Likely ethnicity", 180), ("count", "N", 60), ("pct", "%", 60)):
            self.stat_eth_tree.heading(c, text=t)
            self.stat_eth_tree.column(c, width=w)
        _enable_tree_column_sort(
            self.stat_eth_tree, list(cols),
            labels={"eth": "Likely ethnicity", "count": "N", "pct": "%"},
        )
        self.stat_eth_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        bot = ctk.CTkFrame(tab, fg_color=C["panel"])
        bot.pack(fill="both", expand=True, padx=12, pady=(0, 10))
        ctk.CTkLabel(
            bot, text="By charge category (misclassified only)",
            font=FONT_BOLD, text_color=C["text"],
        ).pack(anchor="w", padx=10, pady=(10, 4))
        ccols = ("cat", "count", "pct")
        self.stat_charge_tree = ttk.Treeview(
            bot, columns=ccols, show="headings", height=8, style="Dark.Treeview"
        )
        for c, t, w in (("cat", "Charge category", 200), ("count", "N", 60), ("pct", "%", 60)):
            self.stat_charge_tree.heading(c, text=t)
            self.stat_charge_tree.column(c, width=w)
        _enable_tree_column_sort(
            self.stat_charge_tree, list(ccols),
            labels={"cat": "Charge category", "count": "N", "pct": "%"},
        )
        self.stat_charge_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _update_statistics(self) -> None:
        results = self._mc_results or []
        meta = self._mc_meta or {}
        n = len(results)
        base = int(meta.get("eth_base") or 0)
        total = int(meta.get("db_total") or 0)
        rate = (n / base * 100.0) if base else 0.0
        if hasattr(self, "stat_db"):
            self.stat_db.configure(text=f"DB: {total:,}")
            self.stat_base.configure(text=f"Ethnicity matches: {base:,}")
            self.stat_n.configure(text=f"Misclassified: {n:,}")
            self.stat_rate.configure(text=f"Rate: {rate:.1f}%")
            self.stat_filter.configure(
                text=(
                    f"Filter: ethnicity={meta.get('eth_filter') or 'all'} · "
                    f"charge={meta.get('charge_filter') or 'all'} · "
                    f"min conf={meta.get('min_conf', 0.5)}"
                )
            )

        # Black / White / Other buckets (SOR parity)
        buckets = Counter(
            _misclass_race_bucket(mc.expected_race) for mc in results
        )
        lines = []
        for label in ("Black", "White", "Other"):
            c = buckets.get(label, 0)
            pct = (c / n * 100.0) if n else 0.0
            lines.append(f"  {label}: {c:,}  ({pct:.1f}%)")
        if hasattr(self, "stat_race_summary"):
            self.stat_race_summary.configure(
                text="\n".join(lines) if n else "No misclassifications in current filter."
            )

        by_eth = Counter(mc.likely_ethnicity for mc in results)
        if hasattr(self, "stat_eth_tree"):
            self.stat_eth_tree.delete(*self.stat_eth_tree.get_children())
            for eth, c in by_eth.most_common():
                pct = (c / n * 100.0) if n else 0.0
                self.stat_eth_tree.insert(
                    "", "end", values=(eth, c, f"{pct:.1f}%")
                )

        by_ch = Counter(
            category_label((mc.record or {}).get("charge_category") or "unknown")
            for mc in results
        )
        if hasattr(self, "stat_charge_tree"):
            self.stat_charge_tree.delete(*self.stat_charge_tree.get_children())
            for cat, c in by_ch.most_common():
                pct = (c / n * 100.0) if n else 0.0
                self.stat_charge_tree.insert(
                    "", "end", values=(cat, c, f"{pct:.1f}%")
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
        self.search_tree = ttk.Treeview(
            tree_fr, columns=cols, show="headings", style="Dark.Treeview"
        )
        for c, t, w in (
            ("name", "Name", 140), ("race", "Race", 90), ("category", "Category", 120),
            ("charge", "Charge", 240), ("state", "ST", 40), ("date", "Date", 100),
        ):
            self.search_tree.column(c, width=w)
        _enable_tree_column_sort(
            self.search_tree, list(cols),
            labels={
                "name": "Name", "race": "Race", "category": "Category",
                "charge": "Charge", "state": "ST", "date": "Date",
            },
        )
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
            bar, text="Remove duplicates…", command=self._dedupe,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=8)
        ctk.CTkButton(
            bar, text="Reclassify charges", command=self._reclassify_charges,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=4)
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
            preview = db.remove_duplicates_all(
                ["source_url", "name_dob"], dry_run=True, merge_fields=True
            )
            would = int(preview.get("total_deleted") or 0)
            if would <= 0:
                messagebox.showinfo("Dedupe", "No duplicates found (URL / name+DOB).")
                return
            if not messagebox.askyesno(
                "Dedupe",
                f"Delete {would:,} duplicate rows?\n"
                f"(Merges multi-state / multi-charge details onto keeper first.)",
            ):
                return
            r = db.remove_duplicates_all(
                ["source_url", "name_dob"], dry_run=False, merge_fields=True
            )
        finally:
            db.close()
        self.log(
            f"Dedupe deleted {r.get('total_deleted')} "
            f"(merged fields {r.get('total_merged_fields')})"
        )
        self._refresh_integrity()

    def _reclassify_charges(self) -> None:
        db = Database(self.db_path)
        try:
            n = db.reclassify_charges()
        finally:
            db.close()
        self.log(f"Reclassified charges on {n:,} rows")
        self._refresh_integrity()
        messagebox.showinfo("Charges", f"Reclassified {n:,} rows.")

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
