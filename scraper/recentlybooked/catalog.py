"""Discovery helpers for RecentlyBooked state and county listing pages."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import List, Set
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from .client import RecentlyBookedClient

BASE_URL = "https://recentlybooked.com"
_STATE_PATH = re.compile(r"^/([a-z]{2})/?$", re.IGNORECASE)
_COUNTY_PATH = re.compile(r"^/([a-z]{2})/([a-z0-9-]+)/?$", re.IGNORECASE)


def _links(html: str, base_url: str = BASE_URL) -> List[str]:
    """Collect absolute hrefs from an HTML page."""
    soup = BeautifulSoup(html, "html.parser")
    return [
        urljoin(base_url, href)
        for link in soup.select("a[href]")
        if (href := link.get("href"))
    ]


def _sitemap_locs(xml_text: str) -> List[str]:
    """Collect ``<loc>`` URLs from a sitemap XML document."""
    # Strip default namespace so findall("loc") works without Clark notation.
    cleaned = re.sub(r'\sxmlns="[^"]+"', "", xml_text, count=1)
    try:
        root = ET.fromstring(cleaned)
    except ET.ParseError:
        # Fallback: treat as HTML/XML soup with an XML-aware parser if available.
        try:
            soup = BeautifulSoup(xml_text, "xml")
        except Exception:
            soup = BeautifulSoup(xml_text, "html.parser")
        return [loc.get_text(strip=True) for loc in soup.find_all("loc") if loc.get_text(strip=True)]
    locs: List[str] = []
    for el in root.iter():
        tag = el.tag.rsplit("}", 1)[-1].lower()
        if tag == "loc" and el.text and el.text.strip():
            locs.append(el.text.strip())
    return locs


def discover_states(html: str, base_url: str = BASE_URL) -> List[str]:
    """Return sorted two-letter state codes linked from a RecentlyBooked page."""
    states: Set[str] = set()
    for link in _links(html, base_url):
        match = _STATE_PATH.match(urlparse(link).path)
        if match:
            states.add(match.group(1).upper())
    return sorted(states)


def discover_counties(html: str, state: str, base_url: str = BASE_URL) -> List[str]:
    """Return sorted county slugs linked from a state page."""
    wanted_state = state.strip().lower()
    counties: Set[str] = set()
    for link in _links(html, base_url):
        match = _COUNTY_PATH.match(urlparse(link).path)
        if match and match.group(1).lower() == wanted_state:
            counties.add(match.group(2).lower())
    return sorted(counties)


def discover_states_from_homepage(client: RecentlyBookedClient) -> List[str]:
    """Fetch the homepage and discover its state links."""
    return discover_states(client.get(BASE_URL))


def discover_counties_for_state(client: RecentlyBookedClient, state: str) -> List[str]:
    """Fetch a state page and discover county links."""
    state = state.strip().lower()
    return discover_counties(client.get(f"{BASE_URL}/{state}"), state)


def discover_counties_from_sitemap(
    client: RecentlyBookedClient,
    sitemap_url: str = f"{BASE_URL}/sitemaps/sitemap-counties.xml",
) -> List[tuple[str, str]]:
    """Return sorted ``(state, county)`` pairs listed in the county sitemap."""
    pairs: Set[tuple[str, str]] = set()
    for link in _sitemap_locs(client.get(sitemap_url)):
        match = _COUNTY_PATH.match(urlparse(link).path)
        if match:
            pairs.add((match.group(1).upper(), match.group(2).lower()))
    return sorted(pairs)
