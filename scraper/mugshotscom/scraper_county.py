"""County scrape mixin. Re-export split parts."""
from __future__ import annotations

from scraper.mugshotscom.scraper_county_one import MugshotsComOneCountyMixin
from scraper.mugshotscom.scraper_state_all import MugshotsComStateAllMixin


class MugshotsComCountyMixin(MugshotsComOneCountyMixin, MugshotsComStateAllMixin):
    """Keep old import path. No logic here."""
