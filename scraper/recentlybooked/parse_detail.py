"""Detail-page parser for RecentlyBooked."""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from .parse_util import (
    BASE_URL,
    _LABEL_ALIASES,
    _detail_match,
    _name_parts,
    _text,
    apply_booking_dates,
)


def _strong_field_value(strong: Tag) -> Optional[str]:
    """Extract the value that follows a ``<strong>Label:</strong>`` marker."""
    parent = strong.parent
    if parent is None:
        return None
    label_text = strong.get_text(strip=True)
    full = parent.get_text(" ", strip=True)
    if full.lower().startswith(label_text.lower()):
        value = full[len(label_text) :].strip(" :\u00a0")
        return value or None
    if ":" in full:
        value = full.split(":", 1)[1].strip(" \u00a0")
        return value or None
    return None


def _detail_pairs(soup: BeautifulSoup) -> Dict[str, str]:
    values: Dict[str, str] = {}
    containers = soup.select(".mugshot-detail, .detail-grid")
    for container in containers:
        for row in container.select("dt, .detail-row, .detail-item, li"):
            label = _text(row)
            sibling = row.find_next_sibling("dd")
            if row.name == "dt" and sibling:
                value = _text(sibling)
            else:
                label_node = row.select_one(".label, .detail-label, strong, b")
                value_node = row.select_one(".value, .detail-value")
                label = _text(label_node) or label
                value = _text(value_node)
            if not label or not value:
                continue
            normalized = re.sub(r"\s*:\s*$", "", label).strip().lower()
            field = _LABEL_ALIASES.get(normalized)
            if field:
                values[field] = value
    for label in soup.select(".mugshot-detail .label, .detail-grid .label, .detail-label"):
        value = _text(label.find_next_sibling()) or _text(
            label.parent.select_one(".value, .detail-value")
        )
        field = _LABEL_ALIASES.get(re.sub(r"\s*:\s*$", "", _text(label) or "").lower())
        if field and value:
            values[field] = value
    # Production markup: <div class="col-md-6"><strong>Race:</strong> White</div>
    for strong in soup.select(".detail-grid strong, .mugshot-details-flex strong"):
        normalized = re.sub(r"\s*:\s*$", "", _text(strong) or "").strip().lower()
        field = _LABEL_ALIASES.get(normalized)
        if not field or field in values:
            continue
        value = _strong_field_value(strong)
        if value:
            values[field] = value
    return values


def _parse_charge_items(soup: BeautifulSoup) -> tuple[Optional[str], Optional[str]]:
    """Return ``(charge_description, case_number)`` from charge-list items."""
    from scraper.charge_sanitize import pick_charge

    charges: List[str] = []
    case_numbers: List[str] = []
    for item in soup.select(".charges .charge-list li, .charge-list li"):
        text = item.get_text(" ", strip=True)
        code_m = re.search(
            r"Charge Code:\s*(.+?)(?:\s+Charge Description:|\s+Bond:|\s*$)",
            text,
            flags=re.IGNORECASE,
        )
        desc_m = re.search(
            r"Charge Description:\s*(.+?)(?:\s+Bond:|\s*$)",
            text,
            flags=re.IGNORECASE,
        )
        code = " ".join((code_m.group(1) if code_m else "").split()) or None
        desc = " ".join((desc_m.group(1) if desc_m else "").split()) or None
        charge, case_no = pick_charge(code, desc)
        if charge:
            charges.append(charge)
        if case_no:
            case_numbers.append(case_no)
    charge_out = "; ".join(dict.fromkeys(charges)) if charges else None
    case_out = "; ".join(dict.fromkeys(case_numbers)) if case_numbers else None
    return charge_out, case_out


def parse_detail(html: str, source_url: str) -> Dict[str, Any]:
    """Parse a detail page, returning a resilient canonical record dictionary."""
    match = _detail_match(source_url)
    record: Dict[str, Any] = {
        "source_url": source_url,
        "source_system": "recentlybooked",
    }
    if match:
        record["state"] = match.group(1).upper()
        record["county"] = match.group(2).lower()
        record["source_id"] = match.group(3)
        record["facility"] = match.group(4)
        bid = (match.group(5) or "").strip()
        if bid:
            record["booking_id"] = bid
            # Only set constructed photo_url when we have a real booking id;
            # never write None (would wipe a listing-card photo_url on merge).
            record["photo_url"] = (
                f"{BASE_URL}/images/{match.group(4)}/{bid}.webp"
            )
    soup = BeautifulSoup(html, "html.parser")
    name = _text(soup.select_one(".mugshot-name, .mugshot-title, h1"))
    record.update(_name_parts(name))
    record.update(_detail_pairs(soup))
    charges, case_number = _parse_charge_items(soup)
    if charges:
        record["charge_description"] = charges
    if case_number:
        record["case_number"] = case_number
    image = soup.select_one(
        "img.mugshot-image[src], .mugshot-detail img[src], .hero-image img[src]"
    )
    if image and image.get("src"):
        record["photo_url"] = urljoin(source_url, str(image.get("src")))
    apply_booking_dates(record)
    return record
