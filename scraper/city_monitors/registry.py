"""Registry of custom city jail monitors."""
from __future__ import annotations

from typing import Dict, List, Optional

from scraper.city_monitors.base import CityMonitorInfo

CITY_MONITORS: List[CityMonitorInfo] = [
    CityMonitorInfo(
        id="sf_sheriff",
        label="San Francisco Sheriff",
        city="San Francisco",
        state="CA",
        search_url="https://www.sfsheriff.gov/inmate-search",
        available=True,
        notes="HTML POST form. Name, booking date, charge, housing. No race/photo.",
    ),
    CityMonitorInfo(
        id="nyc_doc",
        label="NYC DOC Inmate Lookup",
        city="New York City",
        state="NY",
        search_url="https://a073-ilsweb.nyc.gov/",
        available=True,
        notes="HTML POST form. Name, NYSID, charge, race (coded), facility.",
    ),
    CityMonitorInfo(
        id="hawaii_doc",
        label="Hawaii DOC Offender Search",
        city="Honolulu",
        state="HI",
        search_url="https://corrections.ehawaii.gov/",
        available=True,
        notes="HTML POST form. Name, offender ID, facility, charge. Photo on detail.",
    ),
    CityMonitorInfo(
        id="baltimore_dpscs",
        label="Maryland DPSCS Locator (Baltimore)",
        city="Baltimore",
        state="MD",
        search_url="https://dpscs.maryland.gov/",
        available=False,
        notes="Module pending. No scraper yet.",
    ),
    CityMonitorInfo(
        id="alaska_doc",
        label="Alaska DOC Offender Search",
        city="Anchorage",
        state="AK",
        search_url="https://doc.alaska.gov/",
        available=False,
        notes="Module pending. No scraper yet.",
    ),
]

_BY_ID: Dict[str, CityMonitorInfo] = {m.id: m for m in CITY_MONITORS}


def get_city_monitor(monitor_id: str) -> Optional[CityMonitorInfo]:
    return _BY_ID.get((monitor_id or "").strip().lower())


def list_city_monitors(*, available_only: bool = False) -> List[CityMonitorInfo]:
    if available_only:
        return [m for m in CITY_MONITORS if m.available]
    return list(CITY_MONITORS)
