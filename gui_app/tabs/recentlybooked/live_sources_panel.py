"""Open/close Live Feed sources panel and build checkbox rows."""
from __future__ import annotations

from typing import Dict

import customtkinter as ctk

from gui_app.theme import C, FONT_SM

from .constants import _RB_SOURCE_OPTIONS


class RbLiveSourcesPanelMixin:
    def _rb_live_toggle_sources_menu(self):
        """Open/close an embedded panel (stays open for multi-checkbox clicks)."""
        if getattr(self, "_rb_live_sources_open", False):
            self._rb_live_close_sources_menu()
            return
        self._rb_live_open_sources_menu()

    def _rb_live_close_sources_menu(self) -> None:
        panel = getattr(self, "_rb_live_sources_panel", None)
        if panel is not None:
            try:
                panel.destroy()
            except Exception:
                pass
        self._rb_live_sources_panel = None
        self._rb_live_source_status_labels = {}
        self._rb_live_sources_open = False
        try:
            self.rb_live_sources_btn.configure(
                text=self._rb_live_sources_button_text()
            )
        except Exception:
            pass

    def _rb_live_open_sources_menu(self) -> None:
        parent = getattr(self, "_rb_live_sources_host", None)
        if parent is None:
            return
        self._rb_live_close_sources_menu()

        panel = ctk.CTkFrame(
            parent,
            fg_color=C["elevated"],
            border_width=1,
            border_color=C["border"],
            corner_radius=8,
        )
        panel.pack(fill="x", padx=8, pady=(0, 6))
        self._rb_live_sources_panel = panel
        self._rb_live_sources_open = True
        self._rb_live_source_status_labels: Dict[str, ctk.CTkLabel] = {}

        head = ctk.CTkFrame(panel, fg_color="transparent")
        head.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(
            head, text="Live sources", font=FONT_SM, text_color=C["muted"]
        ).pack(side="left")
        ctk.CTkButton(
            head,
            text="Recheck",
            width=72,
            height=24,
            font=FONT_SM,
            command=self._rb_live_recheck_sources,
        ).pack(side="right")

        body = ctk.CTkFrame(panel, fg_color="transparent")
        body.pack(fill="x", padx=8, pady=(2, 4))

        for sid, label in _RB_SOURCE_OPTIONS:
            base = label.replace(" (unavailable)", "").strip()
            row = ctk.CTkFrame(body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            var = self._rb_live_source_vars[sid]
            ctk.CTkCheckBox(
                row,
                text=base,
                variable=var,
                width=170,
                command=self._rb_live_on_sources_changed,
            ).pack(side="left", padx=(4, 6))
            status_lbl = ctk.CTkLabel(
                row,
                text=self._rb_live_status_token(sid),
                font=FONT_SM,
                text_color=self._rb_live_status_color(sid),
                anchor="w",
            )
            status_lbl.pack(side="left", fill="x", expand=True, padx=(0, 6))
            self._rb_live_source_status_labels[sid] = status_lbl

        ctk.CTkLabel(
            panel,
            text=(
                "Checked sources are polled in parallel. "
                "Status comes from a startup ping — use Recheck to refresh."
            ),
            font=FONT_SM,
            text_color=C["dim"],
            anchor="w",
            justify="left",
            wraplength=900,
        ).pack(fill="x", padx=12, pady=(2, 8))

        try:
            self.rb_live_sources_btn.configure(
                text=self._rb_live_sources_button_text()
            )
        except Exception:
            pass
