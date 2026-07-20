"""Render and save premium shareable arrest mugshot cards."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from PIL import Image, ImageDraw, ImageFont

from gui_app.shared.export_card_fields import (
    _BANNER_RED,
    _BANNER_TEXT,
    _BG,
    _CARD_H,
    _CARD_W,
    _CRIME_PANEL,
    _FOIL,
    _LINE,
    _MUTED,
    _TEXT,
    _WATERMARK,
    arrest_datetime,
    crime,
    load_font,
    location,
    person_name,
)
from gui_app.shared.export_card_fit import plan_crime_panel
from gui_app.shared.export_card_photo import (
    draw_seal_watermark,
    load_mugshot,
    wrap_text,
)
from scraper.searcher import format_race_label

# Layout scale (matches premium HTML card proportions on 1080×1350).
_PAD = 48
_NAME_SIZE = 52
_CRIME_H_MIN = 72
_CRIME_H_MAX = 280
_BANNER_H = 96
_FOOTER_H = 68
_NUMBER_SIZE = 52  # bottom-right export No. — large (SORPA parity)
_PHOTO_H_MIN = 360


def render_export_card(
    record: Mapping[str, Any], *, assign_number: bool = False
) -> Image.Image:
    """Build an RGBA premium share card for *record*.

    ``assign_number`` only for deliberate Desktop exports (never bare preview).
    """
    from gui_app.shared.export_card_fields import arrest_date_label

    canvas = Image.new("RGBA", (_CARD_W, _CARD_H), _BG)
    draw = ImageDraw.Draw(canvas)
    _draw_foil_sheen(canvas)

    name = person_name(record)
    race = format_race_label(str(record.get("race") or "").strip()) or "Unknown"
    loc = location(record)
    cr = crime(record)
    # Footer right: export No.; left can include arrest date
    release_lbl = arrest_datetime(record, assign=assign_number)
    date_lbl = arrest_date_label(record)
    if date_lbl and loc and loc != "Unknown location":
        loc_left = f"{loc}  ·  {date_lbl}"
    elif date_lbl:
        loc_left = date_lbl
    else:
        loc_left = loc

    name_font = load_font(_NAME_SIZE, bold=True)
    footer_font = load_font(22)
    number_font = load_font(_NUMBER_SIZE, bold=True)
    reported_font = load_font(22, bold=True)
    race_font = _load_display_font(48)

    max_text_w = _CARD_W - _PAD * 2
    name_h = _name_block_h(draw, name, name_font, max_text_w)
    # Room left for crime after photo min + fixed chrome.
    fixed_below = (
        20 + name_h + 16 + _BANNER_H + 16 + 16 + _FOOTER_H + _PAD
    )
    crime_budget = max(
        _CRIME_H_MIN,
        min(_CRIME_H_MAX, _CARD_H - _PAD - _PHOTO_H_MIN - fixed_below),
    )
    # Prefer full text: shrink type first, then grow panel (photo shrinks).
    crime_font, crime_line_h, crime_lines, crime_h = plan_crime_panel(
        draw,
        cr,
        max_width=max_text_w - 36,
        max_height=crime_budget,
    )
    crime_h = max(_CRIME_H_MIN, min(crime_budget, max(crime_h, _CRIME_H_MIN)))

    stack_h = fixed_below + crime_h
    photo_top = _PAD
    photo_h = max(_PHOTO_H_MIN, _CARD_H - photo_top - stack_h)
    photo_box = (_CARD_W - _PAD * 2, photo_h)
    photo_rect = (_PAD, photo_top, _PAD + photo_box[0], photo_top + photo_box[1])

    # Photo (rounded clip), then frame stroke on top
    draw.rounded_rectangle(photo_rect, radius=28, fill=(13, 14, 18, 255))
    mug = load_mugshot(record, photo_box).convert("RGBA")
    frame = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    frame.paste(mug, (_PAD, photo_top), mug if mug.mode == "RGBA" else None)
    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle(photo_rect, radius=28, fill=255)
    canvas.paste(frame, (0, 0), mask)
    draw.rounded_rectangle(photo_rect, radius=28, outline=_LINE, width=2)

    # Seal + @DoDeportations on the mug (always; after frame so nothing covers it)
    draw_seal_watermark(
        canvas,
        photo_box=photo_rect,
        text=_WATERMARK,
        seal_opacity=0.05,
        text_opacity=0.22,
    )

    y = photo_top + photo_h + 20
    y = _draw_name(draw, name, y, _PAD, max_text_w, name_font)
    y = _draw_race_banner(
        draw, race, y + 8, _PAD, max_text_w, reported_font, race_font
    )
    y = _draw_crime_panel(
        draw,
        crime_lines,
        y + 12,
        _PAD,
        crime_h,
        crime_font,
        crime_line_h,
    )
    _draw_footer(
        draw,
        loc_left,
        release_lbl,
        y + 14,
        _PAD,
        max_text_w,
        footer_font,
        number_font,
    )
    return canvas


def _load_display_font(size: int) -> ImageFont.ImageFont:
    """Striking condensed face for race value (Bebas-like)."""
    windir = Path(__import__("os").environ.get("WINDIR", r"C:\Windows"))
    for name in ("impact.ttf", "arialbd.ttf", "segoeuib.ttf"):
        path = windir / "Fonts" / name
        try:
            if path.is_file():
                return ImageFont.truetype(str(path), size=size)
        except OSError:
            continue
    return load_font(size, bold=True)


def _name_block_h(draw, name: str, font, max_w: int) -> int:
    lines = wrap_text(draw, name or "—", font, max_w)[:2]
    return max(56, len(lines) * 58)


def _draw_foil_sheen(canvas: Image.Image) -> None:
    """Soft premium foil orb in the upper-right (matches HTML sheen)."""
    overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    # Approximate conic sheen with layered translucent ellipses
    cx, cy = _CARD_W - 80, 40
    for r, col in (
        (220, (240, 206, 132, 28)),
        (160, (142, 123, 224, 22)),
        (110, (95, 216, 224, 18)),
        (70, (217, 142, 107, 20)),
    ):
        od.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col)
    canvas.alpha_composite(overlay)


def _draw_name(draw, name: str, y: int, margin: int, max_w: int, font) -> int:
    for line in wrap_text(draw, name or "—", font, max_w)[:2]:
        draw.text((margin, y), line, font=font, fill=_FOIL)
        y += 58
    return y


def _draw_race_banner(
    draw,
    race: str,
    y: int,
    margin: int,
    max_w: int,
    label_font,
    race_font,
) -> int:
    top = y
    draw.rounded_rectangle(
        (margin, top, _CARD_W - margin, top + _BANNER_H),
        radius=14,
        fill=_BANNER_RED,
        outline=(178, 58, 58, 255),
        width=2,
    )
    label = "Reported As"
    race_txt = (race or "Unknown").upper()
    lb = draw.textbbox((0, 0), label, font=label_font)
    lw, lh = lb[2] - lb[0], lb[3] - lb[1]
    race_lines = wrap_text(draw, race_txt, race_font, max_w - 40)[:1]
    rb = draw.textbbox((0, 0), race_lines[0], font=race_font)
    rw, rh = rb[2] - rb[0], rb[3] - rb[1]
    gap = 4
    block = lh + gap + rh
    cy = top + max(0, (_BANNER_H - block) // 2)
    draw.text(
        ((_CARD_W - lw) // 2, cy - lb[1]),
        label,
        font=label_font,
        fill=(245, 217, 217, 255),
    )
    cy += lh + gap
    draw.text(
        ((_CARD_W - rw) // 2, cy - rb[1]),
        race_lines[0],
        font=race_font,
        fill=_BANNER_TEXT,
    )
    return top + _BANNER_H


def _draw_crime_panel(
    draw,
    lines: list,
    y: int,
    margin: int,
    panel_h: int,
    font,
    line_h: int,
) -> int:
    box = (margin, y, _CARD_W - margin, y + panel_h)
    draw.rounded_rectangle(box, radius=18, fill=_CRIME_PANEL, outline=_LINE, width=2)
    ty = y + 14
    for line in lines or ["—"]:
        draw.text((margin + 18, ty), line, font=font, fill=_TEXT)
        ty += line_h
    return y + panel_h


def _draw_footer(
    draw,
    loc: str,
    date: str,
    y: int,
    margin: int,
    max_w: int,
    font,
    number_font=None,
) -> None:
    draw.line((margin, y, _CARD_W - margin, y), fill=_LINE, width=2)
    ty = y + 12
    left = (loc or "—")[:40]
    right = (date or "—")[:28]
    handle = _WATERMARK
    num_font = number_font or load_font(_NUMBER_SIZE, bold=True)
    draw.text((margin, ty + 6), left.upper(), font=font, fill=_MUTED)
    rb = draw.textbbox((0, 0), right, font=num_font)
    rw = rb[2] - rb[0]
    # Brighter + larger so export No. / date reads clearly on the card
    draw.text(
        (_CARD_W - margin - rw, ty),
        right,
        font=num_font,
        fill=(235, 235, 240, 255),
    )
    # Brand mark centered in footer (same handle as photo watermark)
    handle_font = load_font(20, bold=True)
    hb = draw.textbbox((0, 0), handle, font=handle_font)
    hw = hb[2] - hb[0]
    draw.text(
        ((_CARD_W - hw) // 2, ty + 6),
        handle,
        font=handle_font,
        fill=(200, 200, 210, 255),
    )


