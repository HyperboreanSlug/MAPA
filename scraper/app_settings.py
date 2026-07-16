"""Persistent app settings for Arrest Public Archiver."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_SETTINGS_PATH = Path("data/app_settings.json")

DEFAULTS: Dict[str, Any] = {
    "db_path": "data/arrests.db",
    "backup_on_close": False,
    "backup_dir": "data/backups",
    "max_backups": 10,
    "scrape_auto_import": True,
    "scrape_skip_existing": True,
    "scrape_default_row_limit": 5000,
    # RecentlyBooked
    "rb_with_photos": True,
    "rb_with_html": True,
    "rb_delay": 1.0,
    "rb_threads": 10,
    # DeepFace (local mugshot race model)
    "deepface_auto_setup": True,
    "deepface_auto_warm": True,
    "deepface_detector": "retinaface",
    "deepface_weight_models": "Race",
    "deepface_scan_state": "",
    "deepface_scan_min_conf": "0.75",
    "deepface_scan_limit": "0",
    "deepface_scan_recorded": "WHITE",
    "deepface_scan_faces": "black,indian,asian",
    "deepface_scan_force_rescan": False,
    "deepface_scan_source": "",  # e.g. recentlybooked or blank=all
    # App code auto-update from GitHub (git fetch + ff-only pull on open)
    "auto_update_enabled": True,
    # Public database sync from GitHub Releases (download on all machines;
    # upload only when data/db_publish.allow exists on this machine)
    "db_sync_enabled": True,
    "db_sync_prompted": False,
    "db_sync_on_startup": True,
    "db_sync_repo": "HyperboreanSlug/MAPA",
    "db_sync_tag": "database-latest",
    "db_auto_publish_enabled": True,
    "db_publish_change_threshold": 2500,
}


def load_settings(path: Optional[Path] = None) -> Dict[str, Any]:
    p = Path(path) if path else DEFAULT_SETTINGS_PATH
    settings = deepcopy(DEFAULTS)
    if p.is_file():
        try:
            raw = json.loads(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                for k, v in raw.items():
                    if k in DEFAULTS:
                        settings[k] = v
        except (OSError, json.JSONDecodeError, TypeError):
            pass
    return normalize_settings(settings)


def save_settings(settings: Dict[str, Any], path: Optional[Path] = None) -> Path:
    p = Path(path) if path else DEFAULT_SETTINGS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    clean = normalize_settings({**DEFAULTS, **(settings or {})})
    out = {k: clean[k] for k in DEFAULTS}
    p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def normalize_settings(s: Dict[str, Any]) -> Dict[str, Any]:
    out = deepcopy(DEFAULTS)
    out.update({k: s[k] for k in DEFAULTS if k in s})
    out["db_path"] = str(out.get("db_path") or DEFAULTS["db_path"]).strip() or DEFAULTS["db_path"]
    out["backup_dir"] = (
        str(out.get("backup_dir") or DEFAULTS["backup_dir"]).strip() or DEFAULTS["backup_dir"]
    )
    out["backup_on_close"] = bool(out.get("backup_on_close", False))
    out["scrape_auto_import"] = bool(out.get("scrape_auto_import", True))
    out["scrape_skip_existing"] = bool(out.get("scrape_skip_existing", True))
    out["rb_with_photos"] = bool(out.get("rb_with_photos", True))
    out["rb_with_html"] = bool(out.get("rb_with_html", True))
    out["deepface_auto_setup"] = bool(out.get("deepface_auto_setup", True))
    out["deepface_auto_warm"] = bool(out.get("deepface_auto_warm", True))
    out["deepface_scan_force_rescan"] = bool(out.get("deepface_scan_force_rescan", False))
    out["auto_update_enabled"] = bool(out.get("auto_update_enabled", True))
    out["db_sync_enabled"] = bool(out.get("db_sync_enabled", True))
    out["db_sync_prompted"] = bool(out.get("db_sync_prompted", False))
    out["db_sync_on_startup"] = bool(out.get("db_sync_on_startup", True))
    out["db_auto_publish_enabled"] = bool(out.get("db_auto_publish_enabled", True))
    out["db_sync_repo"] = (
        str(out.get("db_sync_repo") or DEFAULTS["db_sync_repo"]).strip()
        or DEFAULTS["db_sync_repo"]
    )
    out["db_sync_tag"] = (
        str(out.get("db_sync_tag") or DEFAULTS["db_sync_tag"]).strip()
        or DEFAULTS["db_sync_tag"]
    )
    try:
        thr = int(out.get("db_publish_change_threshold", 2500))
    except (TypeError, ValueError):
        thr = 2500
    out["db_publish_change_threshold"] = max(1, min(thr, 1_000_000))
    det = str(out.get("deepface_detector") or "retinaface").strip().lower()
    allowed_det = {
        "retinaface", "opencv", "ssd", "mtcnn", "yunet", "mediapipe", "centerface",
    }
    out["deepface_detector"] = det if det in allowed_det else "retinaface"
    wm = str(out.get("deepface_weight_models") or "Race").strip()
    parts = [p.strip() for p in wm.replace(";", ",").split(",") if p.strip()]
    if "Race" not in parts:
        parts.insert(0, "Race")
    out["deepface_weight_models"] = ",".join(parts)
    try:
        out["max_backups"] = max(0, min(int(out.get("max_backups", 10)), 500))
    except (TypeError, ValueError):
        out["max_backups"] = 10
    try:
        out["scrape_default_row_limit"] = max(0, int(out.get("scrape_default_row_limit", 5000)))
    except (TypeError, ValueError):
        out["scrape_default_row_limit"] = 5000
    try:
        out["rb_delay"] = max(0.0, float(out.get("rb_delay", 1.0)))
    except (TypeError, ValueError):
        out["rb_delay"] = 1.0
    try:
        out["rb_threads"] = max(1, min(int(out.get("rb_threads", 10)), 32))
    except (TypeError, ValueError):
        out["rb_threads"] = 10
    return out
