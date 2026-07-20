"""Crime-panel text fitting: shrink font so all charge text is visible."""
from __future__ import annotations

import re
from typing import List, Tuple

from gui_app.shared.export_card_fields import load_font
from gui_app.shared.export_card_photo import wrap_text

# (font_size, line_height) candidates — prefer large readable type.
_SIZE_STEPS: Tuple[Tuple[int, int], ...] = (
    (42, 40),
    (36, 36),
    (30, 32),
    (26, 28),
    (22, 26),
    (18, 22),
    (16, 20),
)


def wrap_crime_text(draw, text: str, font, max_width: int) -> List[str]:
    """Wrap at middle-dot offense breaks when present."""
    text = " ".join((text or "").split())
    if not text:
        return [""]
    if not re.search(r"\s[·•]\s", text):
        return wrap_text(draw, text, font, max_width)

    parts = [p.strip() for p in re.split(r"\s*[·•]\s*", text) if p.strip()]
    if len(parts) < 2:
        return wrap_text(draw, text, font, max_width)

    lines: List[str] = []
    current = ""
    for part in parts:
        for seg in wrap_text(draw, part, font, max_width):
            if not seg:
                continue
            trial = f"{current} · {seg}" if current else seg
            if current and draw.textlength(trial, font=font) > max_width:
                lines.append(current)
                current = seg
            else:
                current = trial
    if current:
        lines.append(current)
    return lines or [""]


def plan_crime_panel(
    draw,
    text: str,
    *,
    max_width: int,
    max_height: int,
    pad_y: int = 14,
) -> Tuple[object, int, List[str], int]:
    """Return (font, line_h, lines, panel_h) that fits *text* in the panel.

    Shrinks type until every line fits without ellipsis when possible.
    """
    body = " ".join((text or "").split()) or "—"
    inner_h = max(24, max_height - pad_y * 2)
    best = None
    for size, line_h in _SIZE_STEPS:
        font = load_font(size, bold=True)
        lines = wrap_crime_text(draw, body, font, max_width)
        need = len(lines) * line_h
        if need <= inner_h and lines:
            panel_h = pad_y * 2 + need
            # Prefer larger type; first hit in descending size list wins.
            return font, line_h, lines, max(panel_h, 72)
        best = (font, line_h, lines, need)

    # Last resort: use smallest font even if slightly over — caller may grow box.
    font, line_h, lines, need = best  # type: ignore[misc]
    panel_h = pad_y * 2 + need
    return font, line_h, lines, panel_h


def min_crime_panel_height(draw, text: str, max_width: int) -> int:
    """Smallest panel height that can show all charge text (16–42pt)."""
    _, _, _, h = plan_crime_panel(
        draw, text, max_width=max_width, max_height=600, pad_y=14
    )
    return max(72, min(h, 320))
