"""Surname ethnicity / recorded race review."""
from __future__ import annotations

import csv
import threading
from tkinter import filedialog

import customtkinter as ctk

from gui_app.theme import C, FONT_SM
from gui_app.widgets import _enable_tree_column_sort, _stretch_columns, _tree_frame
from scraper.charge_classifications import category_label, list_category_choices
from scraper.searcher import ArrestSearcher


class MisclassifyTabMixin:
    def _build_misclassify(self, tab):
        tab.configure(fg_color=C["surface"])
        controls = ctk.CTkFrame(tab, fg_color=C["panel"])
        controls.pack(fill="x", padx=8, pady=8)
        self.mc_eth = ctk.CTkComboBox(controls, values=["all", "hispanic", "asian", "indian",
            "indian_high_confidence", "african_american", "arabic", "jewish"], width=180)
        self.mc_charge = ctk.CTkComboBox(controls, values=list_category_choices(), width=180,
                                          command=lambda _v: None)
        self.mc_conf = ctk.CTkEntry(controls, width=90, placeholder_text="0.50")
        self.mc_limit = ctk.CTkEntry(controls, width=100, placeholder_text="0 = all")
        for label, widget in (("Ethnicity", self.mc_eth), ("Charge", self.mc_charge),
                              ("Min confidence", self.mc_conf), ("Limit", self.mc_limit)):
            ctk.CTkLabel(controls, text=label, font=FONT_SM, text_color=C["muted"]).pack(side="left", padx=(12, 3), pady=10)
            widget.pack(side="left", padx=(0, 5), pady=10)
        self.mc_eth.set("all"); self.mc_charge.set("all"); self.mc_conf.insert(0, "0.50"); self.mc_limit.insert(0, "0")
        self.mc_analyze_btn = ctk.CTkButton(controls, text="Analyze", command=self._run_misclassify)
        self.mc_analyze_btn.pack(side="left", padx=8)
        ctk.CTkButton(controls, text="Export CSV", command=self._export_misclassify).pack(side="left", padx=4)
        ctk.CTkButton(
            controls,
            text="Classified correctly",
            fg_color=C["success"],
            hover_color="#68b888",
            text_color="#0c0c0e",
            command=lambda: self._browse_mc_verdict("correct"),
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            controls,
            text="Classified incorrectly",
            fg_color=C["danger"],
            hover_color="#c96a6a",
            text_color="#0c0c0e",
            command=lambda: self._browse_mc_verdict("incorrect"),
        ).pack(side="left", padx=4)
        self.mc_status = ctk.CTkLabel(tab, text="Run analysis on a background thread.", text_color=C["muted"])
        self.mc_status.pack(anchor="w", padx=12)
        wrap, self.mc_tree = _tree_frame(tab); wrap.pack(fill="both", expand=True, padx=8, pady=8)
        cols = ["name", "race", "likely", "confidence", "charge_category", "state", "date", "source"]
        self.mc_tree.configure(columns=cols)
        labels = {"name":"Name","race":"Recorded race","likely":"Likely ethnicity","confidence":"Confidence",
                  "charge_category":"Charge category","state":"State","date":"Date","source":"Source"}
        _enable_tree_column_sort(self.mc_tree, cols, labels); _stretch_columns(self.mc_tree, cols, [220,130,150,90,170,60,110,130])
        self._mc_results = []

    def _browse_mc_verdict(self, verdict: str):
        sel = self.mc_tree.selection()
        if not sel or not self._mc_results:
            self.mc_status.configure(text="Select a misclass row first.")
            return
        try:
            idx = self.mc_tree.index(sel[0])
        except Exception:
            return
        if not (0 <= idx < len(self._mc_results)):
            return
        from gui_app.shared.record_sidebar import merge_ethnicity_review_flags

        mc = self._mc_results[idx]
        rec = mc.record or {}
        flags_json = merge_ethnicity_review_flags(rec.get("flags"), verdict)
        rec["flags"] = flags_json
        rid = rec.get("id")
        label = "classified correctly" if verdict == "correct" else "classified incorrectly"
        if rid is not None:
            try:
                self.db.update_arrest(int(rid), {"flags": flags_json})
            except Exception as exc:
                self.mc_status.configure(text=f"Could not save verdict: {exc}")
                return
        self.mc_tree.delete(sel[0])
        self._mc_results.pop(idx)
        kids = self.mc_tree.get_children()
        if kids:
            next_i = min(idx, len(kids) - 1)
            self.mc_tree.selection_set(kids[next_i])
            self.mc_tree.focus(kids[next_i])
            self.mc_tree.see(kids[next_i])
        name = (
            f"{rec.get('first_name') or ''} {rec.get('last_name') or ''}"
        ).strip() or rec.get("full_name") or "—"
        self.mc_status.configure(
            text=f"Marked {name} as {label}. {len(self._mc_results):,} remaining."
        )
        self.log(f"Misclass review: {name} → {label}")

    def _run_misclassify(self, source_system=None):
        if getattr(self, "_mc_busy", False): return
        self._mc_busy = True; self.mc_analyze_btn.configure(state="disabled")
        self.mc_status.configure(text="Analyzing names…")
        eth, charge = self.mc_eth.get(), self.mc_charge.get()
        try: confidence, limit = float(self.mc_conf.get() or .5), int(self.mc_limit.get() or 0)
        except ValueError: confidence, limit = .5, 0
        def work():
            try:
                s = ArrestSearcher(self.db_path)
                rows, base = s.analyze_ethnicities(min_confidence=confidence, limit=limit,
                    ethnicity_filter=None if eth == "all" else eth, charge_category=None if charge == "all" else charge,
                    source_system=source_system, return_base_count=True)
                s.close()
                self.after(0, lambda: self._show_misclassify(rows, base))
            except Exception as exc: self.after(0, lambda: self._misclass_error(exc))
        threading.Thread(target=work, daemon=True).start()

    def _misclass_error(self, exc):
        self._mc_busy = False; self.mc_analyze_btn.configure(state="normal"); self.mc_status.configure(text=f"Analysis failed: {exc}")

    def _show_misclassify(self, rows, base):
        self._mc_results = rows
        self.mc_tree.delete(*self.mc_tree.get_children())
        for mc in rows:
            r = mc.record; name = f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip() or r.get("full_name") or "—"
            self.mc_tree.insert("", "end", values=(name, mc.expected_race, mc.likely_ethnicity, f"{mc.confidence:.2%}",
                category_label(r.get("charge_category") or ""), r.get("state") or "—",
                r.get("arrest_date") or r.get("booking_date") or "—", r.get("source_system") or "—"))
        self._mc_busy = False; self.mc_analyze_btn.configure(state="normal")
        self.mc_status.configure(text=f"{len(rows):,} potential mismatches from {base:,} matching-name records")

    def _export_misclassify(self):
        if not getattr(self, "_mc_results", None): return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if not path: return
        with open(path, "w", newline="", encoding="utf-8") as fh:
            out = csv.writer(fh); out.writerow(["name","recorded_race","likely_ethnicity","confidence","charge_category","state","arrest_date","source"])
            for mc in self._mc_results:
                r = mc.record; out.writerow([r.get("full_name") or f"{r.get('first_name') or ''} {r.get('last_name') or ''}".strip(),
                    mc.expected_race, mc.likely_ethnicity, mc.confidence, r.get("charge_category") or "", r.get("state") or "",
                    r.get("arrest_date") or r.get("booking_date") or "", r.get("source_system") or ""])
        self.mc_status.configure(text=f"Exported {len(self._mc_results):,} rows to {path}")
