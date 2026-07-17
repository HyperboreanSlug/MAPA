"""Field extractors and fonts for export mugshot cards."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping, Optional

from PIL import ImageFont

_WATERMARK = "@DoDeportations"
_SEAL_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "department_of_deportations_seal.png"
)
_CARD_W = 1080
_CARD_H = 1350
# Legacy photo slots (grid/tests); premium layout sizes photo dynamically.
_PHOTO_H = 820
_PHOTO_H_MIN = 560
_PHOTO_TOP = 48
# Premium card palette (matches premium_card_blank.html)
_BG = (10, 11, 14, 255)  # obsidian
_PANEL = (20, 22, 27, 255)
_CRIME_PANEL = (20, 22, 27, 255)
_LINE = (38, 42, 51, 255)
_TEXT = (243, 241, 234, 255)
_MUTED = (139, 143, 153, 255)
_FOIL = (240, 206, 132, 255)  # foil gold for name
_ACCENT = (240, 206, 132, 255)
_BANNER_RED = (140, 31, 31, 255)  # #8C1F1F
_BANNER_TEXT = (255, 255, 255, 255)


def os_environ_get(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def desktop_dir() -> Path:
    home = Path.home()
    for name in ("Desktop", "OneDrive/Desktop", "OneDrive/Рабочий стол"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    desktop = home / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]+", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned) or "arrest"
    return cleaned[:80]


def load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
    windir = Path(os_environ_get("WINDIR", r"C:\Windows"))
    candidates = []
    if bold:
        candidates.extend(
            [
                windir / "Fonts" / "segoeuib.ttf",
                windir / "Fonts" / "arialbd.ttf",
                windir / "Fonts" / "calibrib.ttf",
            ]
        )
    candidates.extend(
        [
            windir / "Fonts" / "segoeui.ttf",
            windir / "Fonts" / "arial.ttf",
            windir / "Fonts" / "calibri.ttf",
        ]
    )
    for path in candidates:
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def person_name(record: Mapping[str, Any]) -> str:
    full = str(record.get("full_name") or "").strip()
    if full:
        return full
    parts = [
        str(record.get("first_name") or "").strip(),
        str(record.get("middle_name") or "").strip(),
        str(record.get("last_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p) or "Unknown"


def location(record: Mapping[str, Any]) -> str:
    county = str(record.get("county") or "").strip()
    state = str(record.get("state") or "").strip().upper()
    city = str(record.get("city") or "").strip()
    bits = []
    if city:
        bits.append(city.title())
    if county:
        c = county.replace("-", " ").replace("_", " ").title()
        if not c.lower().endswith("county"):
            c = f"{c} County"
        bits.append(c)
    if state:
        bits.append(state)
    return ", ".join(bits) or "Unknown location"


def crime(record: Mapping[str, Any], *, max_labels: int = 5) -> str:
    """Descriptive charge line for export cards (plain language when possible).

    Prefers expanded offense text (including recovery from raw_json) over coarse
    table buckets like \"SEX OFFENSE\", so cards state the actual crime.
    """
    from gui_app.shared.export_card_polish import (
        card_charge_text,
        limit_charge_labels,
        polish_card_charge,
    )
    from scraper.charge_expand import expand_charge
    from scraper.charge_summary import summarize_charge

    full = expand_charge(record)
    if full and full != "—":
        polished = polish_card_charge(full)
        if polished:
            return card_charge_text(limit_charge_labels(polished, max_labels))
    summary = summarize_charge(record)
    if summary and summary not in ("—", "OTHER"):
        return card_charge_text(limit_charge_labels(summary, max_labels))
    cat = str(record.get("charge_category") or "").strip()
    return cat.replace("_", " ").title() if cat else "Unknown charge"


def arrest_datetime(record: Mapping[str, Any]) -> str:
    date = str(record.get("arrest_date") or record.get("booking_date") or "").strip()
    time = str(record.get("arrest_time") or "").strip()
    if not date:
        return "Unknown"
    if "T" in date:
        d, _, t = date.partition("T")
        date = d
        if not time and t:
            time = t[:5]
    if time:
        return f"{date} {time}".strip()
    return date
