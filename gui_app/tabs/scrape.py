"""Open-data source scrape tab."""
from __future__ import annotations

import threading

import customtkinter as ctk

from gui_app.theme import C
from scraper.config import SOURCES, get_bulk_sources, get_named_sources, get_source
from scraper.database import Database
from scraper.scrapers.base import ScraperFactory


class ScrapeTabMixin:
    def _build_scrape(self, tab):
        tab.configure(fg_color=C["surface"])
        box = ctk.CTkFrame(tab, fg_color=C["panel"])
        box.pack(fill="x", padx=8, pady=8)
        self.scrape_mode = ctk.CTkComboBox(
            box, values=["named_only", "all_bulk", "source"]
        )
        self.scrape_mode.set("named_only")
        self.scrape_mode.pack(side="left", padx=6, pady=8)
        self.scrape_source = ctk.CTkComboBox(box, values=[s.id for s in SOURCES])
        self.scrape_source.pack(side="left", padx=6, pady=8)
        self.scrape_limit = ctk.CTkEntry(box, placeholder_text="Rows / source")
        self.scrape_limit.insert(
            0, str(self.app_settings.get("scrape_default_row_limit", 5000))
        )
        self.scrape_limit.pack(side="left", padx=6)
        self.scrape_start = ctk.CTkButton(
            box, text="Start scrape", command=self._start_open_data_scrape
        )
        self.scrape_start.pack(side="left", padx=6)
        self.scrape_status = ctk.CTkLabel(
            tab,
            text="Select named-only (recommended), all bulk, or a source.",
            text_color=C["muted"],
        )
        self.scrape_status.pack(anchor="w", padx=12)

    def _start_open_data_scrape(self):
        try:
            limit = int(self.scrape_limit.get() or 0)
        except ValueError:
            self.scrape_status.configure(text="Row limit must be a number.")
            return
        mode = self.scrape_mode.get()
        if mode == "named_only":
            sources = get_named_sources()
        elif mode == "all_bulk":
            sources = get_bulk_sources()
        else:
            src = get_source(self.scrape_source.get())
            sources = [src] if src else []
        db_path = self.db_path
        skip_existing = bool(self.app_settings.get("scrape_skip_existing", True))
        auto_import = bool(self.app_settings.get("scrape_auto_import", True))
        self.scrape_start.configure(state="disabled")
        self.is_running = True

        def work():
            imported = 0
            try:
                db = Database(db_path) if auto_import else None
                try:
                    for src in sources:
                        self.log(f"Scraping {src.id}: {src.name}")
                        scraper = ScraperFactory.create(src.id)
                        try:
                            records = scraper.scrape(row_limit=limit)
                        finally:
                            scraper.close()
                        if auto_import and db is not None and records:
                            r = db.import_records(
                                records, skip_existing_urls=skip_existing
                            )
                            imported += r["imported"]
                            self.log(
                                f"{src.id}: +{r['imported']} imported, "
                                f"{r['skipped']} skipped"
                            )
                finally:
                    if db is not None:
                        db.close()
                self.after(
                    0,
                    lambda: self.scrape_status.configure(
                        text=f"Finished: {imported:,} arrests imported."
                    ),
                )
            except Exception as e:
                self.log(f"Open-data scrape failed: {e}")
                self.after(
                    0, lambda: self.scrape_status.configure(text=f"Failed: {e}")
                )
            finally:
                self.is_running = False
                self.after(
                    0,
                    lambda: (
                        self.scrape_start.configure(state="normal"),
                        self._refresh_db_status(),
                    ),
                )

        threading.Thread(target=work, daemon=True).start()
