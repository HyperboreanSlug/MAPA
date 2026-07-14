"""RecentlyBooked Full Scrape toolbar build (flow layout)."""
from __future__ import annotations

from typing import Any, Dict, List

import customtkinter as ctk

from gui_app.theme import C, FONT_SM

from .full_scrape_flow import FlowRow, after_idle_reflow


class RbFullScrapeBuildMixin:
    def _build_rb_full(self, tab):
        bar = ctk.CTkFrame(tab, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        self._rb_full_bar = bar

        flow = FlowRow(bar, padx=5, pady=4)
        self._rb_full_flow = flow

        def chip():
            return ctk.CTkFrame(flow.host, fg_color="transparent")

        # Source + status from live-feed health probe
        src_chip = chip()
        ctk.CTkLabel(
            src_chip, text="Source", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left", padx=(4, 3), pady=4)
        full_labels = self._rb_full_source_values()
        self.rb_full_source = ctk.CTkComboBox(
            src_chip,
            values=full_labels,
            width=260,
            command=self._rb_full_on_source_change,
        )
        self.rb_full_source.set(full_labels[0] if full_labels else "RecentlyBooked")
        self.rb_full_source.pack(side="left", padx=(0, 4), pady=4)
        flow.add(src_chip)

        self.rb_state = ctk.CTkEntry(
            flow.host, placeholder_text="State (e.g. nj)", width=100
        )
        flow.add(self.rb_state)
        self.rb_county = ctk.CTkEntry(
            flow.host, placeholder_text="County slug (optional)", width=160
        )
        flow.add(self.rb_county)
        self.rb_all = ctk.CTkCheckBox(flow.host, text="All states")
        flow.add(self.rb_all)

        thr_chip = chip()
        ctk.CTkLabel(
            thr_chip, text="Threads", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left", padx=(4, 2), pady=4)
        self.rb_threads = ctk.CTkEntry(thr_chip, width=50)
        self.rb_threads.insert(0, str(self.app_settings.get("rb_threads", 10)))
        self.rb_threads.pack(side="left", padx=(0, 4), pady=4)
        flow.add(thr_chip)

        del_chip = chip()
        ctk.CTkLabel(
            del_chip, text="Delay", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left", padx=(4, 2), pady=4)
        self.rb_full_delay = ctk.CTkEntry(del_chip, width=55)
        self.rb_full_delay.insert(0, str(self.app_settings.get("rb_delay", 1.0)))
        self.rb_full_delay.pack(side="left", padx=(0, 4), pady=4)
        flow.add(del_chip)

        self.rb_cancel = False
        flow.add(
            ctk.CTkButton(flow.host, text="Start", width=70, command=self._rb_full_start)
        )
        flow.add(
            ctk.CTkButton(
                flow.host,
                text="Cancel",
                width=70,
                command=lambda: setattr(self, "rb_cancel", True),
            )
        )

        self.rb_full_hide_no_race_var = ctk.BooleanVar(value=True)
        self.rb_full_hide_no_race = ctk.CTkCheckBox(
            flow.host,
            text="Hide no race",
            variable=self.rb_full_hide_no_race_var,
            command=self._rb_full_on_race_filter_toggle,
        )
        self.rb_full_hide_no_race.select()
        flow.add(self.rb_full_hide_no_race)

        self.rb_full_hide_no_photo_var = ctk.BooleanVar(value=True)
        self.rb_full_hide_no_photo = ctk.CTkCheckBox(
            flow.host,
            text="Hide no photo",
            variable=self.rb_full_hide_no_photo_var,
            command=self._rb_full_on_photo_filter_toggle,
        )
        self.rb_full_hide_no_photo.select()
        flow.add(self.rb_full_hide_no_photo)

        self.rb_full_status = ctk.CTkLabel(
            bar,
            text="Multi-thread counties; set Threads + Delay per request.",
            font=FONT_SM,
            text_color=C["muted"],
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.rb_full_status.pack(fill="x", padx=12, pady=(0, 8))
        bar.bind("<Configure>", lambda e: self._rb_full_on_bar_configure(e), add="+")

        self._rb_full_all: List[Dict[str, Any]] = []
        self._rb_split(
            tab,
            records_attr="_rb_full_records",
            tree_attr="rb_full_tree",
            sidebar_attr="rb_full_sidebar",
        )
        after_idle_reflow(self, flow)
        # Pick up a probe that finished before this lazy tab was built.
        self.after(60, self._rb_full_refresh_source_status)

    def _rb_full_on_bar_configure(self, event) -> None:
        w = int(getattr(event, "width", 0) or 0)
        if w < 80:
            return
        try:
            self.rb_full_status.configure(wraplength=max(200, w - 24))
        except Exception:
            pass
        flow = getattr(self, "_rb_full_flow", None)
        if flow is not None:
            try:
                flow.reflow()
            except Exception:
                pass
