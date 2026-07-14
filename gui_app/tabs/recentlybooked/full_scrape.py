"""RecentlyBooked Full Scrape UI, source selection, and filters."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.theme import C, FONT_SM
from gui_app.widgets import tree_row_bind, tree_rows_reset

from .constants import (
    _BN_UNAVAILABLE_HINT,
    _RB_SOURCE_BY_LABEL,
    _RB_SOURCE_LABELS,
)


class RbFullScrapeMixin:
    def _build_rb_full(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        ctk.CTkLabel(
            bar, text="Source", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left", padx=(6, 3), pady=8)
        full_labels = list(_RB_SOURCE_LABELS) + ["All available (load-balanced)"]
        self.rb_full_source = ctk.CTkComboBox(
            bar,
            values=full_labels,
            width=200,
            command=self._rb_full_on_source_change,
        )
        self.rb_full_source.set("RecentlyBooked")
        self.rb_full_source.pack(side="left", padx=(0, 6), pady=8)
        self.rb_state = ctk.CTkEntry(bar, placeholder_text="State (e.g. nj)", width=100)
        self.rb_county = ctk.CTkEntry(
            bar, placeholder_text="County slug (optional)", width=160
        )
        self.rb_state.pack(side="left", padx=5, pady=8)
        self.rb_county.pack(side="left", padx=5)
        self.rb_all = ctk.CTkCheckBox(bar, text="All states")
        self.rb_all.pack(side="left", padx=5)
        ctk.CTkLabel(bar, text="Threads", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(10, 2)
        )
        self.rb_threads = ctk.CTkEntry(bar, width=50)
        self.rb_threads.insert(0, str(self.app_settings.get("rb_threads", 4)))
        self.rb_threads.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(bar, text="Delay", font=FONT_SM, text_color=C["muted"]).pack(
            side="left", padx=(4, 2)
        )
        self.rb_full_delay = ctk.CTkEntry(bar, width=55)
        self.rb_full_delay.insert(0, str(self.app_settings.get("rb_delay", 1.0)))
        self.rb_full_delay.pack(side="left", padx=(0, 6))
        self.rb_cancel = False
        ctk.CTkButton(bar, text="Start", command=self._rb_full_start).pack(
            side="left", padx=5
        )
        ctk.CTkButton(
            bar, text="Cancel", command=lambda: setattr(self, "rb_cancel", True)
        ).pack(side="left", padx=5)
        self.rb_full_hide_no_race_var = ctk.BooleanVar(value=True)
        self.rb_full_hide_no_race = ctk.CTkCheckBox(
            bar,
            text="Hide no race",
            variable=self.rb_full_hide_no_race_var,
            command=self._rb_full_on_race_filter_toggle,
        )
        self.rb_full_hide_no_race.pack(side="left", padx=5)
        self.rb_full_hide_no_race.select()
        self.rb_full_hide_no_photo_var = ctk.BooleanVar(value=True)
        self.rb_full_hide_no_photo = ctk.CTkCheckBox(
            bar,
            text="Hide no photo",
            variable=self.rb_full_hide_no_photo_var,
            command=self._rb_full_on_photo_filter_toggle,
        )
        self.rb_full_hide_no_photo.pack(side="left", padx=5)
        self.rb_full_hide_no_photo.select()
        self.rb_full_status = ctk.CTkLabel(
            bar,
            text="Multi-thread counties; set Threads + Delay per request.",
            font=FONT_SM,
            text_color=C["muted"],
        )
        self.rb_full_status.pack(side="left", padx=12)
        self._rb_full_all: List[Dict[str, Any]] = []
        self._rb_split(
            tab,
            records_attr="_rb_full_records",
            tree_attr="rb_full_tree",
            sidebar_attr="rb_full_sidebar",
        )

    def _rb_full_source_id(self) -> str:
        label = (
            getattr(self, "rb_full_source", None).get()
            if getattr(self, "rb_full_source", None)
            else "RecentlyBooked"
        )
        if label and "load-balanced" in label.lower():
            return "all"
        return _RB_SOURCE_BY_LABEL.get(label, "recentlybooked")

    def _rb_full_on_source_change(self, _choice=None):
        src = self._rb_full_source_id()
        if src == "all":
            self.rb_state.configure(placeholder_text="State (e.g. fl or Florida)")
            self.rb_county.configure(placeholder_text="County slug (optional)")
            self.rb_full_status.configure(
                text=(
                    "Load-balanced multi-host: counties split across available "
                    "sources; identity dedupe skips mirrored people."
                )
            )
        elif src == "bustednewspaper":
            self.rb_state.configure(placeholder_text="State slug (e.g. texas)")
            self.rb_county.configure(
                placeholder_text="County slug (e.g. brazos-county)"
            )
            self.rb_full_status.configure(
                text=_BN_UNAVAILABLE_HINT
                + " Full scrape will fail fast if SSL is still broken."
            )
        elif src == "mugshotscom":
            self.rb_state.configure(placeholder_text="State (e.g. fl or Florida)")
            self.rb_county.configure(
                placeholder_text="County (e.g. Alachua-County-FL)"
            )
            self.rb_full_status.configure(
                text="Mugshots.com: US-States county pages; Threads = workers per county."
            )
        else:
            self.rb_state.configure(placeholder_text="State (e.g. nj)")
            self.rb_county.configure(placeholder_text="County slug (optional)")
            self.rb_full_status.configure(
                text="Multi-thread counties; set Threads + Delay per request."
            )

    def _rb_full_filter_flags(self) -> tuple[bool, bool]:
        hide_race = bool(
            getattr(self, "rb_full_hide_no_race_var", None)
            and self.rb_full_hide_no_race_var.get()
        )
        hide_photo = bool(
            getattr(self, "rb_full_hide_no_photo_var", None)
            and self.rb_full_hide_no_photo_var.get()
        )
        return hide_race, hide_photo

    def _rb_full_update_filter_status(self, *, log: bool = True) -> None:
        shown = len(self._rb_full_records)
        total = len(getattr(self, "_rb_full_all", []) or [])
        hide_race, hide_photo = self._rb_full_filter_flags()
        mode = self._rb_filter_mode_text(
            hide_no_race=hide_race, hide_no_photo=hide_photo
        )
        self.rb_full_status.configure(
            text=f"Full scrape: {shown}/{total} shown ({mode})."
        )
        if log:
            self.log(f"Full scrape filter: {mode} ({shown}/{total}).")

    def _rb_full_on_race_filter_toggle(self):
        self._rb_rebuild_full_tree()
        self._rb_full_update_filter_status()

    def _rb_full_on_photo_filter_toggle(self):
        self._rb_rebuild_full_tree()
        self._rb_full_update_filter_status()

    def _rb_rebuild_full_tree(self, *, select_url: Optional[str] = None) -> None:
        eth = getattr(self, "_rb_full_eth", None)
        all_rows = getattr(self, "_rb_full_all", []) or []
        hide_race, hide_photo = self._rb_full_filter_flags()
        shown = self._rb_filter_rows(
            all_rows,
            hide_no_race=hide_race,
            hide_no_photo=hide_photo,
        )
        self._rb_full_records = shown
        self.rb_full_tree.delete(*self.rb_full_tree.get_children())
        tree_rows_reset(self.rb_full_tree)
        select_item = None
        select_rec = None
        for rec in shown:
            item = self.rb_full_tree.insert(
                "", "end", values=self._rb_row_values(rec, eth)
            )
            tree_row_bind(self.rb_full_tree, item, rec)
            if select_url and str(rec.get("source_url") or "") == select_url:
                select_item = item
                select_rec = rec
        if select_item:
            self.rb_full_tree.selection_set(select_item)
            self.rb_full_tree.see(select_item)
            self.rb_full_sidebar.show(select_rec)
        elif not shown:
            self.rb_full_sidebar.clear("No rows match filter.")
