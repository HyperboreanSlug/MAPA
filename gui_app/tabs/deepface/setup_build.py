"""DeepFace Setup sub-tab: status, options, and install buttons UI."""
from __future__ import annotations

import queue
import sys

import customtkinter as ctk

from gui_app.theme import C, FONT_MONO, FONT_SM
from gui_app.widgets import _card, _muted, _section_label, _wire_wide_scroll


class DeepfaceSetupBuildMixin:
    def _build_deepface_setup(self, tab) -> None:
        """Build scrollable status / options / weights UI (lazy, no TF import)."""
        if getattr(self, "_df_setup_built", False):
            return
        self._df_setup_built = True
        self._df_built = True
        self._df_tab = tab

        root = ctk.CTkScrollableFrame(
            tab,
            fg_color=C["surface"],
            corner_radius=0,
            border_width=0,
        )
        root.pack(fill="both", expand=True, padx=8, pady=8)
        _wire_wide_scroll(tab, root)
        self._df_scroll = root

        self._build_deepface_setup_status(root)
        self._build_deepface_setup_options(root)
        self._build_deepface_setup_weights(root)
        self._build_deepface_setup_log(root, tab)

    def _build_deepface_setup_status(self, root) -> None:
        status_card = _card(root)
        status_card.pack(fill="x", padx=4, pady=(4, 8))
        _section_label(status_card, "DeepFace status").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        _muted(
            status_card,
            "Local open-source face race model (no cloud). Scan defaults to FairFace; "
            "DeepFace is legacy fallback. Used by mugshot verify/scan.",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        self.df_status_installed = ctk.CTkLabel(
            status_card, text="Installed: —", font=FONT_SM, text_color=C["text"], anchor="w",
        )
        self.df_status_installed.pack(fill="x", padx=14, pady=2)
        self.df_status_backend = ctk.CTkLabel(
            status_card, text="Backend: —", font=FONT_SM, text_color=C["text"], anchor="w",
        )
        self.df_status_backend.pack(fill="x", padx=14, pady=2)
        self.df_status_backends = ctk.CTkLabel(
            status_card, text="Available: —", font=FONT_SM, text_color=C["muted"], anchor="w",
        )
        self.df_status_backends.pack(fill="x", padx=14, pady=2)
        self.df_status_python = ctk.CTkLabel(
            status_card,
            text=f"Interpreter: {sys.executable}",
            font=FONT_MONO, text_color=C["dim"], anchor="w",
            wraplength=900, justify="left",
        )
        self.df_status_python.pack(fill="x", padx=14, pady=(2, 4))
        self.df_status_weights = ctk.CTkLabel(
            status_card, text="Weights cache: —", font=FONT_SM, text_color=C["muted"], anchor="w",
        )
        self.df_status_weights.pack(fill="x", padx=14, pady=(0, 10))

        btn_row = ctk.CTkFrame(status_card, fg_color="transparent")
        btn_row.pack(fill="x", padx=14, pady=(0, 12))
        ctk.CTkButton(
            btn_row, text="Refresh status", width=120,
            command=self._deepface_refresh_status,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Open setup log", width=120,
            command=self._deepface_open_log,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            btn_row, text="Open weights folder", width=140,
            command=self._deepface_open_weights_dir,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left")

    def _build_deepface_setup_options(self, root) -> None:
        opt_card = _card(root)
        opt_card.pack(fill="x", padx=4, pady=(0, 8))
        _section_label(opt_card, "Setup options").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        _muted(
            opt_card,
            "Controls automatic install when the app starts and when mugshot tools run. "
            "Does not block the VBS launcher.",
        ).pack(anchor="w", padx=14, pady=(0, 8))

        sett = getattr(self, "app_settings", {}) or {}
        self.df_auto_setup = ctk.BooleanVar(
            value=bool(sett.get("deepface_auto_setup", True))
        )
        self.df_auto_warm = ctk.BooleanVar(
            value=bool(sett.get("deepface_auto_warm", True))
        )
        ctk.CTkCheckBox(
            opt_card,
            text="Auto-install DeepFace on app start (background)",
            variable=self.df_auto_setup, font=FONT_SM, text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], checkmark_color=C["bg"],
            command=self._deepface_save_options,
        ).pack(anchor="w", padx=14, pady=4)
        ctk.CTkCheckBox(
            opt_card,
            text="Warm selected weights after install (download once to ~/.deepface/weights)",
            variable=self.df_auto_warm, font=FONT_SM, text_color=C["text"],
            fg_color=C["accent"], hover_color=C["accent_hover"],
            border_color=C["border"], checkmark_color=C["bg"],
            command=self._deepface_save_options,
        ).pack(anchor="w", padx=14, pady=(0, 10))

        act = ctk.CTkFrame(opt_card, fg_color="transparent")
        act.pack(fill="x", padx=14, pady=(0, 8))
        self.df_install_btn = ctk.CTkButton(
            act, text="Install / repair packages", width=160,
            command=lambda: self._deepface_run_setup(warm=True),
            fg_color=C["accent"], hover_color=C["accent_hover"], text_color=C["bg"],
        )
        self.df_install_btn.pack(side="left", padx=(0, 8))
        self.df_warm_btn = ctk.CTkButton(
            act, text="Download selected weights", width=170,
            command=self._deepface_download_selected_weights,
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        )
        self.df_warm_btn.pack(side="left", padx=(0, 8))
        ctk.CTkButton(
            act, text="Packages only (no weights)", width=160,
            command=lambda: self._deepface_run_setup(warm=False),
            fg_color=C["elevated"], hover_color=C["border"], text_color=C["text"],
            border_width=1, border_color=C["border"],
        ).pack(side="left")

        self.df_job_status = ctk.CTkLabel(
            opt_card, text="", font=FONT_SM, text_color=C["dim"], anchor="w",
        )
        self.df_job_status.pack(fill="x", padx=14, pady=(0, 12))

    def _build_deepface_setup_log(self, root, tab) -> None:
        log_card = _card(root)
        log_card.pack(fill="x", padx=4, pady=(0, 8))
        _section_label(log_card, "Setup activity").pack(
            anchor="w", padx=14, pady=(12, 4)
        )
        self.df_log = ctk.CTkTextbox(
            log_card, height=220, font=FONT_MONO, fg_color=C["bg"],
            text_color=C["muted"], border_color=C["border"],
            border_width=1, corner_radius=8,
        )
        self.df_log.pack(fill="x", expand=False, padx=12, pady=(0, 12))
        self.df_log.configure(state="disabled")
        self._df_log_queue: queue.Queue = queue.Queue()
        self._df_setup_running = False

        self.after(50, self._deepface_refresh_status)
        self.after(100, self._deepface_poll_log)
        self.after(150, lambda: self._deepface_bind_scroll_children(tab, root))
