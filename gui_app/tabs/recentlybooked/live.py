"""Live feed bar. Uses FlowRow so controls wrap on narrow windows."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import customtkinter as ctk

from gui_app.theme import C, FONT_SM

from .constants import (
    _RB_LIVE_DEFAULT_SOURCES,
    _RB_LIVE_POLL_MS,
    _RB_SOURCE_OPTIONS,
)
from .full_scrape_flow import FlowRow, after_idle_reflow


class RbLiveMixin:
    def _build_rb_live(self, tab):
        # Host holds toolbar and drop-down panel. No pop-up window.
        self._rb_live_sources_host = ctk.CTkFrame(tab, fg_color="transparent")
        self._rb_live_sources_host.pack(fill="x")

        bar = ctk.CTkFrame(self._rb_live_sources_host, fg_color=C["panel"])
        bar.pack(fill="x", padx=8, pady=8)
        self._rb_live_bar = bar
        flow = FlowRow(bar, padx=5, pady=4)
        self._rb_live_flow = flow
        refresh_btn = ctk.CTkButton(
            flow.host, text="Refresh", command=lambda: self._rb_refresh(False)
        )
        # Keep source check boxes. Load defaults first.
        self._rb_live_source_vars: Dict[str, ctk.BooleanVar] = {}
        for sid, _label in _RB_SOURCE_OPTIONS:
            self._rb_live_source_vars[sid] = ctk.BooleanVar(
                value=(sid in _RB_LIVE_DEFAULT_SOURCES)
            )
        self._rb_live_sources_panel = None
        self._rb_live_sources_open = False
        self._rb_live_source_status_labels = {}
        self._rb_live_health_synced = False
        if not hasattr(self, "_source_health") or self._source_health is None:
            self._source_health = {}
        self.rb_live_sources_btn = ctk.CTkButton(
            flow.host,
            text=self._rb_live_sources_button_text(),
            width=170,
            command=self._rb_live_toggle_sources_menu,
        )
        self.rb_live_auto_var = ctk.BooleanVar(value=True)
        self.rb_live_auto = ctk.CTkCheckBox(
            flow.host,
            text="Auto-update",
            variable=self.rb_live_auto_var,
            command=self._rb_live_on_auto_toggle,
        )
        self.rb_live_hide_no_race_var = ctk.BooleanVar(value=True)
        self.rb_live_hide_no_race = ctk.CTkCheckBox(
            flow.host,
            text="Hide no race",
            variable=self.rb_live_hide_no_race_var,
            command=self._rb_live_on_race_filter_toggle,
        )
        self.rb_live_hide_no_race.select()
        self.rb_live_hide_no_photo_var = ctk.BooleanVar(value=True)
        self.rb_live_hide_no_photo = ctk.CTkCheckBox(
            flow.host,
            text="Hide no photo",
            variable=self.rb_live_hide_no_photo_var,
            command=self._rb_live_on_photo_filter_toggle,
        )
        self.rb_live_hide_no_photo.select()
        for w in (
            refresh_btn,
            self.rb_live_sources_btn,
            self.rb_live_auto,
            self.rb_live_hide_no_race,
            self.rb_live_hide_no_photo,
        ):
            flow.add(w)
        # Keep status outside flow. Long text must not break wrap.
        self.rb_live_status = ctk.CTkLabel(
            bar,
            text="Live feed auto-imports every booking it shows.",
            font=FONT_SM,
            text_color=C["muted"],
            anchor="w",
            justify="left",
            wraplength=900,
        )
        self.rb_live_status.pack(fill="x", padx=12, pady=(0, 8))
        bar.bind("<Configure>", self._rb_live_on_bar_configure, add="+")
        after_idle_reflow(self, flow)
        self._rb_live_all: List[Dict[str, Any]] = []
        self._rb_live_busy = False
        self._rb_live_poll_after = None
        self._rb_split(
            tab,
            records_attr="_rb_records",
            tree_attr="rb_tree",
            sidebar_attr="rb_live_sidebar",
        )
        # Refresh status labels if a startup probe already finished.
        self.after(50, self._rb_live_refresh_source_status_ui)
        self.after(200, lambda: self._rb_refresh(False))
        self.after(_RB_LIVE_POLL_MS, self._rb_live_tick)

    def _rb_live_on_bar_configure(self, event) -> None:
        # Grow wrap width with bar. Reflow controls.
        w = int(getattr(event, "width", 0) or 0)
        if w < 80:
            return
        try:
            self.rb_live_status.configure(wraplength=max(200, w - 24))
        except Exception:
            pass
        flow = getattr(self, "_rb_live_flow", None)
        if flow is not None:
            try:
                flow.reflow()
            except Exception:
                pass

    def _rb_live_on_auto_toggle(self):
        if self.rb_live_auto_var.get():
            self.log_live("Live feed: auto-update on.")
            if not self._rb_live_busy:
                self._rb_refresh(True)
        else:
            self.log_live("Live feed: auto-update off.")
