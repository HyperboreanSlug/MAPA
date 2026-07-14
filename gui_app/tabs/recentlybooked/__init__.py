"""RecentlyBooked live feed, misclassify, and full scrape."""
from __future__ import annotations

import customtkinter as ctk

from gui_app.lazy_tabs import LazyTabHost
from gui_app.theme import C

from .common import RbCommonMixin
from .full_scrape import RbFullScrapeMixin
from .full_scrape_dispatch import RbFullScrapeDispatchMixin
from .full_scrape_run import RbFullScrapeRunMixin
from .full_scrape_ui import RbFullScrapeUiMixin
from .full_scrape_worker import RbFullScrapeWorkerMixin
from .live import RbLiveMixin
from .live_fetch import RbLiveFetchMixin
from .live_filters import RbLiveFiltersMixin
from .live_refresh import RbLiveRefreshMixin
from .live_sources import RbLiveSourcesMixin
from .live_sources_panel import RbLiveSourcesPanelMixin
from .misclassify import RbMisclassifyMixin
from .misclassify_analyze import RbMisclassifyAnalyzeMixin
from .verdicts import RbVerdictsMixin


class RecentlyBookedTabMixin(
    RbLiveRefreshMixin,
    RbLiveFetchMixin,
    RbLiveFiltersMixin,
    RbLiveSourcesPanelMixin,
    RbLiveSourcesMixin,
    RbLiveMixin,
    RbMisclassifyAnalyzeMixin,
    RbMisclassifyMixin,
    RbFullScrapeWorkerMixin,
    RbFullScrapeUiMixin,
    RbFullScrapeDispatchMixin,
    RbFullScrapeRunMixin,
    RbFullScrapeMixin,
    RbVerdictsMixin,
    RbCommonMixin,
):
    def _build_recentlybooked(self, tab):
        tab.configure(fg_color=C["surface"])
        view = ctk.CTkTabview(
            tab,
            fg_color=C["surface"],
            segmented_button_fg_color=C["elevated"],
            segmented_button_selected_color=C["accent_dim"],
        )
        view.pack(fill="both", expand=True, padx=6, pady=6)
        host = LazyTabHost(view)
        host.register("Live Feed", self._build_rb_live)
        host.register("Misclassify", self._build_rb_misclassify)
        host.register("Full Scrape", self._build_rb_full)
        view.set("Live Feed")
        host.ensure("Live Feed")
        return host


__all__ = ["RecentlyBookedTabMixin"]
