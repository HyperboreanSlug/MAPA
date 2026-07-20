"""Compose a shareable arrest mugshot card and save it to the Desktop."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from gui_app.shared.export_card_fields import (
    os_environ_get,
    person_name as _person_name,
    desktop_dir as _desktop_dir,
    safe_filename as _safe_filename,
    load_font as _load_font,
    location as _location,
    crime as _crime,
    arrest_datetime as _arrest_datetime,
    desktop_dir,
    person_name,
    safe_filename,
)
from gui_app.shared.export_card_photo import (
    resolve_photo_path as _resolve_photo_path,
    load_mugshot as _load_mugshot,
    is_backdrop as _is_backdrop,
    is_rope_gold as _is_rope_gold,
    prepared_seal as _prepared_seal,
    load_seal as _load_seal,
    with_opacity as _with_opacity,
    wrap_text as _wrap_text,
    draw_seal_watermark as _draw_seal_watermark,
)
from gui_app.shared.export_card_render import render_export_card


def export_record_card_to_desktop(record: Mapping[str, Any]) -> Path:
    """Render and save a PNG card to the user's Desktop; return the path.

    Deliberate export: mints export No., marks confirmed incorrect (SORPA parity).
    """
    img = render_export_card(record, assign_number=True)
    desktop = desktop_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name = safe_filename(person_name(record) or "arrest")
    out = desktop / f"{name}_{stamp}.png"
    n = 1
    while out.exists():
        out = desktop / f"{name}_{stamp}_{n}.png"
        n += 1
    img.convert("RGB").save(out, format="PNG", optimize=True)
    try:
        from gui_app.shared.export_card_confirm import (
            mark_export_confirmed_incorrect,
        )

        mark_export_confirmed_incorrect(record)
    except Exception:
        pass
    return out


__all__ = [
    "render_export_card",
    "export_record_card_to_desktop",
    "os_environ_get",
    "_person_name",
    "_desktop_dir",
    "_safe_filename",
    "_load_font",
    "_location",
    "_crime",
    "_arrest_datetime",
    "_resolve_photo_path",
    "_load_mugshot",
    "_is_backdrop",
    "_is_rope_gold",
    "_prepared_seal",
    "_load_seal",
    "_with_opacity",
    "_wrap_text",
    "_draw_seal_watermark",
]
