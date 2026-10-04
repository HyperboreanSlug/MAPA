"""Photo download helpers for mugshots.com records."""

from __future__ import annotations

import re
import threading
from pathlib import Path
from typing import Any, Mapping, Optional
from urllib.parse import urlparse

from scraper.mugshot_ethnicity.photo_quality import (
    bytes_non_mugshot_reason,
    is_placeholder_photo,
    is_placeholder_photo_url,
)

from .client import MugshotsComClient

_guard = threading.Lock()
_url_local: dict[str, Path] = {}
_url_skip: set[str] = set()
_MAX_CACHE = 50_000


def reset_photo_cache() -> None:
    """Clear in-memory photo URL caches (call between scrape sessions)."""
    with _guard:
        _url_local.clear()
        _url_skip.clear()


def _safe_id(record: Mapping[str, Any]) -> str:
    sid = str(record.get("source_id") or "").strip()
    if sid:
        return re.sub(r"[^\w.-]+", "_", sid)[:80]
    url = str(record.get("source_url") or "")
    base = urlparse(url).path.rsplit("/", 1)[-1]
    base = re.sub(r"\.html?$", "", base, flags=re.I)
    return re.sub(r"[^\w.-]+", "_", base)[:80] or "unknown"


def download_photo(
    record: Mapping[str, Any],
    client: Optional[MugshotsComClient] = None,
    output_root: Path | str = Path("data/photos/mugshotscom"),
) -> Optional[Path]:
    photo_url = str(record.get("photo_url") or "").strip()
    if not photo_url or is_placeholder_photo_url(photo_url):
        return None
    with _guard:
        if photo_url in _url_skip:
            return None
        cached = _url_local.get(photo_url)
    if cached is not None and cached.is_file() and not is_placeholder_photo(cached):
        return cached

    from scraper.paths import safe_fs_part, safe_join
    state = safe_fs_part(record.get("state"), fallback="xx")
    county = safe_fs_part(record.get("county"), fallback="unknown")
    ext = ".jpg"
    path_l = photo_url.lower()
    if ".webp" in path_l:
        ext = ".webp"
    elif ".png" in path_l:
        ext = ".png"
    destination = safe_join(Path(output_root), state, county) / f"{_safe_id(record)}{ext}"
    if destination.is_file() and not is_placeholder_photo(destination):
        with _guard:
            if len(_url_local) >= _MAX_CACHE:
                _url_local.clear()
            _url_local[photo_url] = destination
        return destination

    own = client is None
    http = client or MugshotsComClient()
    try:
        data = http.get_bytes(photo_url, referer=str(record.get("source_url") or ""))
        reason = bytes_non_mugshot_reason(data, url=photo_url, ext=ext)
        if reason:
            with _guard:
                _url_skip.add(photo_url)
            return None
        destination.parent.mkdir(parents=True, exist_ok=True)
        tmp = destination.with_suffix(destination.suffix + ".partial")
        tmp.write_bytes(data)
        tmp.replace(destination)
        if is_placeholder_photo(destination):
            try:
                destination.unlink()
            except OSError:
                pass
            with _guard:
                _url_skip.add(photo_url)
            return None
        with _guard:
            if len(_url_local) >= _MAX_CACHE:
                _url_local.clear()
            _url_local[photo_url] = destination
        return destination
    finally:
        if own:
            http.close()
