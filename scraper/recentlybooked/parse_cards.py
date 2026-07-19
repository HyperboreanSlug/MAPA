"""Listing card parsers for RecentlyBooked."""
from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .parse_util import (
    BASE_URL,
    _detail_match,
    _name_parts,
    _text,
    apply_booking_dates,
)


def _card_href(card: Tag) -> Optional[str]:
    """Resolve a booking detail href from county or homepage card markup."""
    link = (
        card.select_one("a.mugshot-card-link[href]")
        or card.select_one("a.mugshot-link[href]")
        or card.select_one('a[href*="~"]')
    )
    if link is not None and link.get("href"):
        return str(link.get("href"))
    if card.name == "a" and card.get("href"):
        return str(card.get("href"))
    data_href = card.get("data-href")
    if data_href:
        return str(data_href)
    return None


def _record_from_card(card: Tag, base_url: str) -> Optional[Dict[str, Any]]:
    href = _card_href(card)
    if not href:
        return None
    source_url = urljoin(base_url, href)
    match = _detail_match(source_url)
    if match is None:
        return None

    name = _text(card.select_one(".mugshot-name"))
    record: Dict[str, Any] = {
        **_name_parts(name),
        "state": match.group(1).upper(),
        "county": match.group(2).lower(),
        "source_url": source_url,
        "source_id": match.group(3),
        "source_system": "recentlybooked",
        "facility": match.group(4),
        "booking_id": match.group(5) or None,
    }
    booking_date = _text(card.select_one(".mugshot-date"))
    if booking_date:
        record["booking_date"] = booking_date
        apply_booking_dates(record)
    location = _text(card.select_one(".mugshot-location"))
    if location:
        record["location"] = location
    image = card.select_one("img.mugshot-image[src], .mugshot-image img[src]")
    if image:
        record["photo_url"] = urljoin(base_url, str(image.get("src")))
    elif match.group(5):
        record["photo_url"] = f"{BASE_URL}/images/{match.group(4)}/{match.group(5)}.webp"
    return record


def _parse_cards(html: str, base_url: str) -> List[Dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    cards: Iterable[Tag] = soup.select(".mugshot-card")
    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for card in cards:
        record = _record_from_card(card, base_url)
        if record and record["source_url"] not in seen:
            seen.add(record["source_url"])
            records.append(record)
    return records


def parse_live_feed(html: str, base_url: str = BASE_URL) -> List[Dict[str, Any]]:
    """Parse booking cards from the RecentlyBooked homepage."""
    return _parse_cards(html, base_url)


def parse_county_cards(html: str, base_url: str = BASE_URL) -> List[Dict[str, Any]]:
    """Parse booking cards from a county listing page."""
    return _parse_cards(html, base_url)
