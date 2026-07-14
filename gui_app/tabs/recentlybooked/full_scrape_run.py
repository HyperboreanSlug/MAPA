"""RecentlyBooked Full Scrape start: validate, settings, launch worker."""
from __future__ import annotations

import threading

from .constants import _BN_UNAVAILABLE_HINT


class RbFullScrapeRunMixin:
    def _rb_full_start(self):
        self.rb_cancel = False
        state = self.rb_state.get().strip()
        county = self.rb_county.get().strip()
        scrape_all = bool(self.rb_all.get())
        source_id = self._rb_full_source_id()
        if not scrape_all and not state:
            self.log("Enter a state or enable All states.")
            return

        db_path = self.db_path
        try:
            delay = max(0.0, float(self.rb_full_delay.get().strip() or 1.0))
        except ValueError:
            delay = float(self.app_settings.get("rb_delay") or 1.0)
        try:
            workers = max(1, min(int(self.rb_threads.get().strip() or 10), 32))
        except ValueError:
            workers = int(self.app_settings.get("rb_threads") or 10)
        if source_id == "bustednewspaper":
            workers = 1
            self.log(_BN_UNAVAILABLE_HINT)
            self.rb_full_status.configure(text=_BN_UNAVAILABLE_HINT)
        self.app_settings["rb_delay"] = delay
        self.app_settings["rb_threads"] = workers
        try:
            from scraper.app_settings import save_settings

            save_settings(self.app_settings)
        except Exception:
            pass
        with_photos = True
        with_html = bool(self.app_settings.get("rb_with_html", True))
        if source_id == "all":
            source_label = "Multi-host (load-balanced)"
        elif source_id == "bustednewspaper":
            source_label = "Busted Newspaper"
        elif source_id == "mugshotscom":
            source_label = "Mugshots.com"
        else:
            source_label = "RecentlyBooked"

        self._rb_full_all = []
        self._rb_full_records = []
        self.rb_full_tree.delete(*self.rb_full_tree.get_children())
        self.rb_full_sidebar.clear("Scraping…")
        self.rb_full_status.configure(
            text=f"Starting {source_label} ({workers} threads, delay {delay}s)…"
        )
        self.log(
            f"{source_label} full scrape started "
            f"({workers} threads, delay {delay}s)…"
        )

        cfg = dict(
            db_path=db_path,
            state=state,
            county=county,
            scrape_all=scrape_all,
            source_id=source_id,
            source_label=source_label,
            delay=delay,
            workers=workers,
            with_photos=with_photos,
            with_html=with_html,
        )
        threading.Thread(
            target=lambda: self._rb_full_scrape_worker(cfg),
            daemon=True,
        ).start()
