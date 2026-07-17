"""DeepFace tab shell + Scan sub-tab layout orchestration."""
from __future__ import annotations

from typing import Optional

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.theme import C
from gui_app.widgets import _card, _muted, _section_label


class DeepfaceScanBuildMixin:
    def _build_deepface(self, tab):
        """Nested sub-tabs: Scan (primary) and Setup (status / weights / install)."""
        tab.configure(fg_color=C["surface"])
        self._df_status_busy = False
        self._df_setup_built = False
        self._df_scan_running = False
        self._df_scan_cancel = False
        self._df_scan_hits: list = []

        sub = ctk.CTkTabview(
            tab,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
            segmented_button_selected_hover_color=C["select"],
            segmented_button_unselected_color=C["elevated"],
            segmented_button_unselected_hover_color=C["panel"],
            text_color=C["text"],
            corner_radius=10,
            border_width=0,
        )
        sub.pack(fill="both", expand=True, padx=6, pady=6)
        self.deepface_tabs = sub

        host = LazyTabHost(sub, on_change=self._on_deepface_subtab_change)
        self._deepface_lazy = host
        host.register("Scan", lambda p: self._build_deepface_scan(p) or True)
        host.register("Setup", lambda p: self._build_deepface_setup(p) or True)

        try:
            sub.set("Scan")
        except Exception:
            pass
        host.ensure("Scan")
        return host

    def _on_deepface_subtab_change(self, name: Optional[str] = None) -> None:
        try:
            name = name or self.deepface_tabs.get()
        except Exception:
            name = "Scan"
        if name == "Setup" and hasattr(self, "_deepface_refresh_status"):
            if getattr(self, "_df_setup_built", False):
                try:
                    self.after(30, self._deepface_refresh_status)
                except Exception:
                    pass

    def _build_deepface_scan(self, tab) -> None:
        """Scan options, start/stop, progress, and results monitor."""
        tab.configure(fg_color=C["surface"])
        sett = getattr(self, "app_settings", {}) or {}

        tab.grid_columnconfigure(0, weight=1)
        tab.grid_rowconfigure(1, weight=1)

        top = ctk.CTkFrame(tab, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(6, 4))
        top.grid_columnconfigure(0, weight=1)

        opt = _card(top)
        opt.pack(fill="x", padx=2, pady=2)
        _section_label(opt, "Mugshot gross-misclass scan").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        _muted(
            opt,
            "Score mugshots with FairFace by default (DeepFace only if FairFace is "
            "unavailable). Flags high-confidence face ethnicity that contradicts the "
            "registry race (default: face Black/Indian/Asian while race is White). "
            "Does not use surnames. Setup still manages DeepFace weights as fallback.",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        self._build_deepface_scan_form(opt, sett)
        self._build_deepface_scan_controls(opt)

        bottom = ctk.CTkFrame(tab, fg_color="transparent")
        bottom.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        bottom.grid_columnconfigure(0, weight=3)
        bottom.grid_columnconfigure(1, weight=3)
        bottom.grid_columnconfigure(2, weight=2)
        bottom.grid_rowconfigure(0, weight=1)

        self._build_deepface_scan_panels(bottom)
