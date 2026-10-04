"""Photo archival helpers for Busted Newspaper records."""

from __future__ import annotations

import shutil
import threading
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Set
from urllib.parse import urlparse

from scraper.mugshot_ethnicity.photo_quality import (
    bytes_non_mugshot_reason,
    is_placeholder_photo,
    is_placeholder_photo_url,
)

from .client import BustedNewspaperClient

_guard = threading.Lock()
_path_locks: Dict[str, threading.Lock] = {}
_url_locks: Dict[str, threading.Lock] = {}
_url_local: Dict[str, Path] = {}
_url_skip: Set[str] = set()


def _lock_for(table: Dict[str, threading.Lock], key: str) -> threading.Lock:
    with _guard:
        lock = table.get(key)
        if lock is None:
            lock = threading.Lock()
            table[key] = lock
        return lock


def _mark_skip(photo_url: str) -> None:
    with _guard:
        _url_skip.add(photo_url)
        _url_local.pop(photo_url, None)


def _remember(photo_url: str, path: Path) -> None:
    with _guard:
        _url_local[photo_url] = path
        _url_skip.discard(photo_url)


def _cached_local(photo_url: str) -> Optional[Path]:
    with _guard:
        if photo_url in _url_skip:
            return None
        path = _url_local.get(photo_url)
    if path is not None and path.is_file() and not is_placeholder_photo(path):
        return path
    return None


def _should_skip_url(photo_url: str) -> bool:
    with _guard:
        return photo_url in _url_skip


def _photo_extension(photo_url: str) -> str:
    path = urlparse(photo_url).path.lower()
    for ext in (".webp", ".jpg", ".jpeg", ".png"):
        if path.endswith(ext):
            return ext
    return ".jpg"


def _link_or_copy(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return
    try:
        os_link = getattr(Path, "hardlink_to", None)
        if os_link is not None:
            dest.hardlink_to(src)
            return
    except OSError:
        pass
    try:
        import os

        os.link(src, dest)
        return
    except OSError:
        pass
    shutil.copy2(src, dest)


def _atomic_write(destination: Path, data: bytes) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(destination.name + ".partial")
    try:
        tmp.write_bytes(data)
        tmp.replace(destination)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass


def download_photo(
    record: Mapping[str, Any],
    client: Optional[BustedNewspaperClient] = None,
    output_root: Path | str = Path("data/photos/bustednewspaper"),
) -> Optional[Path]:
    """Download a record's photo and return its archive path, or ``None`` if absent."""
    from scraper.paths import safe_fs_part, safe_join
    photo_url = str(record.get("photo_url") or "").strip()
    state = safe_fs_part(record.get("state"), fallback="")
    county = safe_fs_part(record.get("county"), fallback="")
    source_id = safe_fs_part(record.get("source_id"), fallback="")
    if not photo_url or not state or not county or not source_id:
        return None
    if is_placeholder_photo_url(photo_url) or _should_skip_url(photo_url):
        _mark_skip(photo_url)
        return None

    existing = str(record.get("photo_path") or "").strip()
    if existing:
        existing_path = Path(existing)
        if existing_path.is_file() and not is_placeholder_photo(existing_path):
            _remember(photo_url, existing_path)
            return existing_path

    ext = _photo_extension(photo_url)
    destination = safe_join(Path(output_root), state, county) / f"{source_id}{ext}"
    dest_key = str(destination).lower()
    path_lock = _lock_for(_path_locks, dest_key)

    with path_lock:
        if destination.exists():
            if is_placeholder_photo(destination):
                try:
                    destination.unlink()
                except OSError:
                    pass
            else:
                _remember(photo_url, destination)
                return destination

        cached = _cached_local(photo_url)
        if cached is not None:
            if cached.resolve() != destination.resolve():
                _link_or_copy(cached, destination)
            if destination.exists() and not is_placeholder_photo(destination):
                _remember(photo_url, destination)
                return destination

        url_lock = _lock_for(_url_locks, photo_url)
        with url_lock:
            if _should_skip_url(photo_url):
                return None
            cached = _cached_local(photo_url)
            if cached is not None:
                if cached.resolve() != destination.resolve():
                    _link_or_copy(cached, destination)
                if destination.exists() and not is_placeholder_photo(destination):
                    _remember(photo_url, destination)
                    return destination

            if destination.exists() and not is_placeholder_photo(destination):
                _remember(photo_url, destination)
                return destination

            own_client = client is None
            http = client or BustedNewspaperClient()
            try:
                data = http.get_bytes(photo_url)
                reason = bytes_non_mugshot_reason(data, url=photo_url, ext=ext)
                if reason:
                    _mark_skip(photo_url)
                    return None
                _atomic_write(destination, data)
                if is_placeholder_photo(destination):
                    try:
                        destination.unlink()
                    except OSError:
                        pass
                    _mark_skip(photo_url)
                    return None
                _remember(photo_url, destination)
                return destination
            finally:
                if own_client:
                    http.close()
