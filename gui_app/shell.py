"""Application shell for Arrest Public Archiver."""
from __future__ import annotations

import queue
from pathlib import Path
from typing import Any, Dict

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.shell_health import SourceHealthMixin
from gui_app.theme import C, FONT_SM, FONT_TITLE, style_treeview
from gui_app.tabs.browse import BrowseTabMixin
from gui_app.tabs.browse.deepface_reports import DeepfaceReportsTabMixin
from gui_app.tabs.browse.integrity import IntegrityTabMixin
from gui_app.tabs.browse.misclassify import MisclassifyTabMixin
from gui_app.tabs.browse.search import SearchTabMixin
from gui_app.tabs.browse.statistics import StatisticsTabMixin
from gui_app.tabs.deepface import DeepfaceTabMixin
from gui_app.tabs.recentlybooked import RecentlyBookedTabMixin
from gui_app.tabs.scrape import ScrapeTabMixin
from gui_app.tabs.settings import SettingsTabMixin
from scraper.app_settings import load_settings, save_settings
from scraper.database import Database, backup_database_file


class ArrestArchiverApp(
    SourceHealthMixin,
    BrowseTabMixin,
    MisclassifyTabMixin,
    StatisticsTabMixin,
    SearchTabMixin,
    IntegrityTabMixin,
    DeepfaceReportsTabMixin,
    RecentlyBookedTabMixin,
    DeepfaceTabMixin,
    ScrapeTabMixin,
    SettingsTabMixin,
    ctk.CTk,
):
    """Top-level window and shared database/settings lifecycle."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Arrest Public Archiver")
        self.geometry("1320x860")
        self.minsize(940, 650)
        self.app_settings = load_settings()
        self.db_path = str(self.app_settings["db_path"])
        self.db = Database(self.db_path)
        self.log_queue: queue.Queue[str] = queue.Queue()
        self.is_running = False
        self._source_health: Dict[str, Dict[str, Any]] = {}
        self._source_health_busy = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        style_treeview(self)

        header = ctk.CTkFrame(self, fg_color=C["panel"], corner_radius=0)
        header.pack(fill="x")
        ctk.CTkLabel(
            header,
            text="Arrest Public Archiver",
            font=FONT_TITLE,
            text_color=C["text"],
        ).pack(side="left", padx=18, pady=12)
        self.db_status = ctk.CTkLabel(
            header, text="", font=FONT_SM, text_color=C["muted"]
        )
        self.db_status.pack(side="right", padx=18)
        self._refresh_db_status()

        tabs = ctk.CTkTabview(
            self,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
            segmented_button_selected_hover_color=C["select"],
        )
        tabs.pack(fill="both", expand=True, padx=10, pady=(8, 4))
        self.tab_host = LazyTabHost(tabs, on_change=lambda _n: self._drain_log())
        self.tab_host.register("Browse", self._build_browse)
        self.tab_host.register("RecentlyBooked", self._build_recentlybooked)
        self.tab_host.register("DeepFace", self._build_deepface)
        self.tab_host.register("Scrape", self._build_scrape)
        self.tab_host.register("Settings", self._build_settings)
        tabs.set("Browse")
        self.tab_host.ensure("Browse")

        self.activity_log = ctk.CTkTextbox(
            self, height=110, fg_color=C["bg"], text_color=C["muted"], font=FONT_SM
        )
        self.activity_log.pack(fill="x", padx=10, pady=(0, 10))
        self.after(250, self._drain_log)
        # Ping mugshot hosts in the background so Live Feed can show real status.
        self.after(100, lambda: self._start_source_health_probe(force=False))

    def log(self, message: str) -> None:
        self.log_queue.put(str(message))

    def _drain_log(self) -> None:
        try:
            while True:
                self.activity_log.insert(
                    "end", self.log_queue.get_nowait().rstrip() + "\n"
                )
                self.activity_log.see("end")
        except queue.Empty:
            pass
        try:
            self.after(250, self._drain_log)
        except Exception:
            pass

    def _refresh_db_status(self) -> None:
        try:
            count = self.db.get_total_count()
            self.db_status.configure(text=f"{self.db_path}  ·  {count:,} arrests")
        except Exception as exc:
            self.db_status.configure(text=f"Database unavailable: {exc}")

    def reopen_database(self, path: str) -> None:
        self.db.close()
        self.db_path = str(Path(path))
        self.db = Database(self.db_path)
        self.app_settings["db_path"] = self.db_path
        save_settings(self.app_settings)
        self._refresh_db_status()

    def _on_close(self) -> None:
        try:
            if self.app_settings.get("backup_on_close"):
                backup_database_file(
                    self.db_path,
                    self.app_settings.get("backup_dir", "data/backups"),
                    keep=self.app_settings.get("max_backups", 10),
                    open_db=self.db,
                )
            save_settings(self.app_settings)
            self.db.close()
        finally:
            self.destroy()
