"""Compose a shareable arrest mugshot card and save it to the Desktop."""

from __future__ import annotations

import re
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from scraper.searcher import format_race_label

_WATERMARK = "@DoDeportations"
_SEAL_PATH = (
    Path(__file__).resolve().parents[2] / "assets" / "department_of_deportations_seal.png"
)
_CARD_W = 1080
_CARD_H = 1350
_PHOTO_H = 820
_BG = (12, 12, 14, 255)
_PANEL = (26, 26, 32, 255)
_TEXT = (236, 236, 241, 255)
_MUTED = (155, 155, 168, 255)
_ACCENT = (232, 168, 124, 255)
_BANNER_RED = (180, 28, 36, 255)
_BANNER_TEXT = (255, 255, 255, 255)


def _desktop_dir() -> Path:
    home = Path.home()
    for name in ("Desktop", "OneDrive/Desktop", "OneDrive/Рабочий стол"):
        candidate = home / name
        if candidate.is_dir():
            return candidate
    desktop = home / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    return desktop


def _safe_filename(name: str) -> str:
    cleaned = re.sub(r"[^\w\s\-]+", "", name, flags=re.UNICODE).strip()
    cleaned = re.sub(r"\s+", "_", cleaned) or "arrest"
    return cleaned[:80]


def _load_font(size: int, *, bold: bool = False) -> ImageFont.ImageFont:
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


def os_environ_get(key: str, default: str = "") -> str:
    import os

    return os.environ.get(key, default)


def _person_name(record: Mapping[str, Any]) -> str:
    full = str(record.get("full_name") or "").strip()
    if full:
        return full
    parts = [
        str(record.get("first_name") or "").strip(),
        str(record.get("middle_name") or "").strip(),
        str(record.get("last_name") or "").strip(),
    ]
    return " ".join(p for p in parts if p) or "Unknown"


def _location(record: Mapping[str, Any]) -> str:
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


def _crime(record: Mapping[str, Any]) -> str:
    charge = str(record.get("charge_description") or "").strip()
    if charge:
        return charge
    cat = str(record.get("charge_category") or "").strip()
    return cat.replace("_", " ").title() if cat else "Unknown charge"


def _arrest_datetime(record: Mapping[str, Any]) -> str:
    """Best-effort arrest/booking date (+ time when available)."""
    date = str(
        record.get("arrest_date") or record.get("booking_date") or ""
    ).strip()
    time = str(record.get("arrest_time") or "").strip()
    if not date:
        return "Unknown"
    # Trim ISO timestamps like "2026-07-12T14:03:00" to date (+ time).
    if "T" in date:
        d, _, t = date.partition("T")
        date = d
        if not time and t:
            time = t[:5]
    if time:
        return f"{date} {time}".strip()
    return date


def _resolve_photo_path(raw: Any) -> Optional[Path]:
    text = str(raw or "").strip()
    if not text:
        return None
    path = Path(text)
    if path.is_file():
        return path
    alt = Path.cwd() / path
    if alt.is_file():
        return alt
    return path if path.exists() else None


def _load_mugshot(record: Mapping[str, Any], box: Tuple[int, int]) -> Image.Image:
    path = _resolve_photo_path(record.get("photo_path"))
    img: Optional[Image.Image] = None
    if path and path.is_file():
        try:
            img = Image.open(path)
            if getattr(img, "n_frames", 1) > 1:
                img.seek(0)
            img = img.convert("RGB")
        except Exception:
            img = None
    if img is None:
        url = str(record.get("photo_url") or "").strip()
        if url and "mugshot-placeholder" not in url.lower():
            try:
                import requests
                from scraper.config import USER_AGENT

                resp = requests.get(
                    url,
                    timeout=25,
                    headers={
                        "User-Agent": USER_AGENT,
                        "Accept": "image/webp,image/*,*/*;q=0.8",
                        "Referer": "https://recentlybooked.com/",
                    },
                )
                resp.raise_for_status()
                import io

                img = Image.open(io.BytesIO(resp.content)).convert("RGB")
            except Exception:
                img = None
    if img is None:
        placeholder = Image.new("RGB", box, (34, 34, 42))
        draw = ImageDraw.Draw(placeholder)
        font = _load_font(42, bold=True)
        msg = "NO PHOTO"
        bbox = draw.textbbox((0, 0), msg, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text(
            ((box[0] - tw) / 2, (box[1] - th) / 2),
            msg,
            font=font,
            fill=(120, 120, 130),
        )
        return placeholder
    return ImageOps.fit(img, box, method=Image.Resampling.LANCZOS, centering=(0.5, 0.35))


def _wrap_text(
    draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        trial = f"{current} {word}"
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _is_backdrop(r: int, g: int, b: int) -> bool:
    """True for seal square backdrop (black or parchment), not navy/gold art."""
    # Solid black plate behind the circular seal.
    if r <= 28 and g <= 28 and b <= 28:
        return True
    mx, mn = max(r, g, b), min(r, g, b)
    avg = (r + g + b) / 3.0
    # Older parchment/tan plate.
    if mx - mn <= 70 and 120 <= avg <= 230 and r >= b - 5 and g >= b - 10:
        return True
    return False


def _is_rope_gold(r: int, g: int, b: int) -> bool:
    """True for the outer twisted gold/bronze rope border."""
    if b > 110:
        return False
    if r < 70 and g < 60:
        return False
    # Gold/bronze: red+green dominate blue, warm bias.
    if r >= g >= b and (r - b) >= 35 and (g - b) >= 15:
        return True
    if r >= 90 and g >= 60 and b <= 100 and (r + g) > 2.2 * (b + 1):
        return True
    return False


@lru_cache(maxsize=4)
def _prepared_seal(path_str: str, mtime_ns: int) -> Image.Image:
    """Load seal with backdrop + outer rope made transparent."""
    import math

    im = Image.open(path_str).convert("RGBA")
    w, h = im.size
    cx, cy = (w - 1) / 2.0, (h - 1) / 2.0
    max_r = min(cx, cy)
    # Drop outer rope + square backdrop; keep navy disc + artwork.
    rope_start = max_r * 0.875
    px = im.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            dist = math.hypot(x - cx, y - cy)
            if dist > rope_start or _is_backdrop(r, g, b):
                px[x, y] = (r, g, b, 0)
                continue
            # Any leftover rope fragments just inside the cut.
            if dist > max_r * 0.82 and _is_rope_gold(r, g, b):
                px[x, y] = (r, g, b, 0)
    return im


def _load_seal() -> Optional[Image.Image]:
    if not _SEAL_PATH.is_file():
        return None
    try:
        st = _SEAL_PATH.stat()
        return _prepared_seal(str(_SEAL_PATH.resolve()), int(getattr(st, "st_mtime_ns", 0))).copy()
    except Exception:
        try:
            return Image.open(_SEAL_PATH).convert("RGBA")
        except Exception:
            return None


def _with_opacity(img: Image.Image, opacity: float) -> Image.Image:
    """Multiply existing alpha by *opacity* (0..1)."""
    rgba = img.convert("RGBA")
    r, g, b, a = rgba.split()
    factor = max(0.0, min(1.0, float(opacity)))
    a = a.point(lambda p: int(round(p * factor)))
    out = Image.merge("RGBA", (r, g, b, a))
    return out


def _draw_seal_watermark(
    canvas: Image.Image,
    *,
    photo_box: Tuple[int, int, int, int],
    text: str = _WATERMARK,
    seal_opacity: float = 0.03,
    text_opacity: float = 0.15,
) -> None:
    """Center the Department seal on the mugshot with handle text beneath it."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    left, top, right, bottom = photo_box
    photo_w = max(1, right - left)
    photo_h = max(1, bottom - top)

    seal = _load_seal()
    if seal is not None:
        # Cover the mugshot (scale-to-cover + clip). alpha_composite keeps
        # the intended opacity (paste(..., mask=self) multiplies alpha down).
        seal = ImageOps.fit(
            seal,
            (photo_w, photo_h),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        seal = _with_opacity(seal, seal_opacity)
        overlay.alpha_composite(seal, dest=(left, top))
        text_top = top + photo_h - max(48, photo_h // 12)
    else:
        text_top = top + photo_h // 2

    draw = ImageDraw.Draw(overlay)
    font = _load_font(max(36, photo_w // 14), bold=True)
    alpha = max(1, int(round(255 * text_opacity)))
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    tx = left + (photo_w - tw) // 2
    ty = min(bottom - th - 12, max(top + 8, text_top))
    draw.text((tx, ty), text, font=font, fill=(255, 255, 255, alpha))
    canvas.alpha_composite(overlay)


def render_export_card(record: Mapping[str, Any]) -> Image.Image:
    """Build an RGBA share card for *record*."""
    canvas = Image.new("RGBA", (_CARD_W, _CARD_H), _BG)
    draw = ImageDraw.Draw(canvas)

    # Photo panel
    margin = 48
    photo_box = (_CARD_W - margin * 2, _PHOTO_H)
    photo_rect = (margin, margin, margin + photo_box[0], margin + photo_box[1])
    mug = _load_mugshot(record, photo_box).convert("RGBA")
    canvas.paste(mug, (margin, margin), mug if mug.mode == "RGBA" else None)

    # Seal at 3%; mugshot @handle at 15%
    _draw_seal_watermark(
        canvas, photo_box=photo_rect, seal_opacity=0.03, text_opacity=0.15
    )

    # Accent bar under photo
    bar_y = margin + _PHOTO_H + 18
    draw.rounded_rectangle(
        (margin, bar_y, _CARD_W - margin, bar_y + 8),
        radius=4,
        fill=_ACCENT,
    )

    name = _person_name(record)
    race = format_race_label(str(record.get("race") or "").strip()) or "Unknown"
    location = _location(record)
    crime = _crime(record)
    arrest_dt = _arrest_datetime(record)

    name_font = _load_font(54, bold=True)
    label_font = _load_font(26)
    value_font = _load_font(34, bold=True)
    banner_font = _load_font(48, bold=True)

    y = bar_y + 28
    max_text_w = _CARD_W - margin * 2

    for line in _wrap_text(draw, name, name_font, max_text_w)[:2]:
        draw.text((margin, y), line, font=name_font, fill=_TEXT)
        y += 62

    # Big red race banner
    y += 12
    banner_h = 108
    banner_pad_x = 28
    draw.rounded_rectangle(
        (margin, y, _CARD_W - margin, y + banner_h),
        radius=14,
        fill=_BANNER_RED,
    )
    banner_label_font = _load_font(24, bold=True)
    label = "RACE MARKED"
    lb = draw.textbbox((0, 0), label, font=banner_label_font)
    lw = lb[2] - lb[0]
    draw.text(
        ((_CARD_W - lw) // 2, y + 14),
        label,
        font=banner_label_font,
        fill=(255, 220, 220, 255),
    )
    race_lines = _wrap_text(draw, race.upper(), banner_font, max_text_w - banner_pad_x * 2)[:2]
    line_h = 50 if len(race_lines) > 1 else 54
    text_block_h = line_h * len(race_lines)
    ty = y + 42 + max(0, (banner_h - 42 - text_block_h) // 2)
    for line in race_lines:
        bbox = draw.textbbox((0, 0), line, font=banner_font)
        tw = bbox[2] - bbox[0]
        draw.text(
            ((_CARD_W - tw) // 2, ty),
            line,
            font=banner_font,
            fill=_BANNER_TEXT,
        )
        ty += line_h
    y += banner_h + 22

    def section(label: str, value: str, top: int) -> int:
        draw.text((margin, top), label.upper(), font=label_font, fill=_MUTED)
        top += 34
        for line in _wrap_text(draw, value, value_font, max_text_w)[:3]:
            draw.text((margin, top), line, font=value_font, fill=_TEXT)
            top += 42
        return top + 10

    def two_col_section(
        left_label: str,
        left_value: str,
        right_label: str,
        right_value: str,
        top: int,
    ) -> int:
        gutter = 32
        col_w = (max_text_w - gutter) // 2
        right_x = margin + col_w + gutter
        draw.text((margin, top), left_label.upper(), font=label_font, fill=_MUTED)
        draw.text((right_x, top), right_label.upper(), font=label_font, fill=_MUTED)
        head = top + 34
        left_lines = _wrap_text(draw, left_value, value_font, col_w)[:3]
        right_lines = _wrap_text(draw, right_value, value_font, col_w)[:3]
        ly = head
        for line in left_lines:
            draw.text((margin, ly), line, font=value_font, fill=_TEXT)
            ly += 42
        ry = head
        for line in right_lines:
            draw.text((right_x, ry), line, font=value_font, fill=_TEXT)
            ry += 42
        return max(ly, ry) + 10

    y = two_col_section(
        "Arrest location", location, "Arrest date", arrest_dt, y
    )
    y = section("Crime", crime, y)

    # Bottom-right handle at 100% opacity
    handle = _WATERMARK
    handle_font = _load_font(28, bold=True)
    hb = draw.textbbox((0, 0), handle, font=handle_font)
    hw, hh = hb[2] - hb[0], hb[3] - hb[1]
    draw.text(
        (_CARD_W - margin - hw, _CARD_H - margin - hh),
        handle,
        font=handle_font,
        fill=(255, 255, 255, 255),
    )

    return canvas


def export_record_card_to_desktop(record: Mapping[str, Any]) -> Path:
    """Render and save a PNG card to the user's Desktop; return the path."""
    img = render_export_card(record)
    desktop = _desktop_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = _safe_filename(_person_name(record))
    out = desktop / f"{name}_{stamp}.png"
    # Avoid clobbering if same-second export
    n = 1
    while out.exists():
        out = desktop / f"{name}_{stamp}_{n}.png"
        n += 1
    img.convert("RGB").save(out, format="PNG", optimize=True)
    return out
