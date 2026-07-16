"""Body of public DB sync: base install, deltas, selective photos."""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scraper.db_sync_base_install import (
    count_arrests as _count_arrests,
    install_base_from_zip as _install_base_from_zip,
    write_sync_stamp as _write_stamp,
)
from scraper.db_sync_common import *  # noqa: F401,F403
from scraper.db_sync_part1 import _http_download_file, _log, resolve_release_urls
from scraper.db_sync_part2 import (
    _load_stamp,
    _photos_present_locally,
    pending_delta_specs,
    photo_parts_needing_download,
)
from scraper.db_sync_part3_deltas import apply_pending_deltas
from scraper.db_sync_part3_photos import download_needed_photos
from scraper.db_sync_progress import OverallProgress, estimate_sync_weights


def run_db_sync(
    dest: Path,
    *,
    remote: Optional[Dict[str, Any]],
    repo: str,
    tag: str,
    project_root: Path,
    log: Optional[Callable[[str], None]],
    apply_delta_zip: Callable,
) -> SyncResult:
    stamp = _load_stamp(dest)
    zip_url, _, extra_urls = resolve_release_urls(repo=repo, tag=tag)
    base = f"https://github.com/{repo}/releases/download/{tag}"

    photo_specs: List[Dict[str, Any]] = []
    if remote and isinstance(remote.get("photos"), list):
        photo_specs = [
            p for p in remote["photos"] if isinstance(p, dict) and p.get("name")
        ]
    if not photo_specs:
        for name in sorted(extra_urls):
            if name.startswith(PHOTO_ASSET_PREFIX):
                photo_specs.append({"name": name, "sha256": None})
    for spec in photo_specs:
        name = str(spec["name"])
        if name not in extra_urls:
            extra_urls[name] = f"{base}/{name}"

    remote_sha = (remote or {}).get("sha256")
    base_matches = bool(
        dest.is_file()
        and dest.stat().st_size > 1000
        and stamp.get("remote_sha256")
        and remote_sha
        and stamp.get("remote_sha256") == remote_sha
    )
    if base_matches and stamp.get("base_id") and (remote or {}).get("base_id"):
        base_matches = stamp.get("base_id") == (remote or {}).get("base_id")

    pending = pending_delta_specs(remote, stamp) if base_matches else []
    need_base = not base_matches
    need_photos = photo_parts_needing_download(remote, stamp) if photo_specs else []
    if (
        not need_base
        and remote
        and remote.get("includes_photos")
        and not _photos_present_locally(dest)
        and photo_specs
    ):
        need_photos = photo_specs

    existed = dest.is_file() and dest.stat().st_size > 1000
    tmp_dir = Path(tempfile.mkdtemp(prefix="sor_db_sync_"))
    photos_extracted = 0
    bytes_written = 0
    deltas_applied = 0
    applied_deltas: List[str] = (
        list(stamp.get("applied_deltas") or []) if base_matches else []
    )
    local_photo_parts: Dict[str, str] = dict(stamp.get("local_photo_parts") or {})
    if not isinstance(local_photo_parts, dict):
        local_photo_parts = {}
    n = 0

    base_weight, delta_weights, photo_weights, extract_weight, install_weight = (
        estimate_sync_weights(
            need_base=need_base,
            remote=remote,
            pending=pending,
            need_photos=need_photos,
        )
    )
    progress = OverallProgress(
        base_weight
        + sum(delta_weights)
        + sum(photo_weights)
        + extract_weight
        + install_weight,
        log=log,
    )
    if progress.total > 0:
        progress.report("Starting database sync", force=True)

    try:
        if need_base:
            zip_path = tmp_dir / "arrests.db.zip"
            _log(log, f"Downloading base database {zip_url} …")
            try:
                _http_download_file(
                    zip_url,
                    zip_path,
                    timeout=600.0,
                    expected_sha256=remote_sha,
                    log=log,
                    label="database zip",
                    progress=progress,
                    progress_weight=base_weight,
                )
            except Exception as e:
                return SyncResult(False, "error", f"Base download failed: {e}")
            bytes_written += zip_path.stat().st_size
            try:
                n = _install_base_from_zip(zip_path, dest, log)
                if install_weight:
                    progress.advance(install_weight, "Installed base database")
            except Exception as e:
                return SyncResult(False, "error", f"Base install failed: {e}")
            applied_deltas = []
            pending = []
            if remote and isinstance(remote.get("deltas"), list):
                pending = [
                    d
                    for d in remote["deltas"]
                    if isinstance(d, dict) and d.get("name")
                ]
                # Recompute delta weights if full base brought the whole chain
                extra = sum(
                    int(d.get("size_bytes") or 0) or 2_000_000 for d in pending
                )
                if extra:
                    progress.add_total(extra)
        else:
            n = _count_arrests(dest) or int(stamp.get("local_record_count") or 0)

        da, db, names, derr = apply_pending_deltas(
            dest,
            pending,
            extra_urls=extra_urls,
            base=base,
            tmp_dir=tmp_dir,
            apply_delta_zip=apply_delta_zip,
            log=log,
            progress=progress,
        )
        if derr is not None:
            return derr
        deltas_applied = da
        bytes_written += db
        applied_deltas.extend(names)

        if deltas_applied or need_base:
            n = _count_arrests(dest) or n

        pe, pb, err = download_needed_photos(
            need_photos,
            extra_urls=extra_urls,
            base=base,
            tmp_dir=tmp_dir,
            project_root=project_root,
            local_photo_parts=local_photo_parts,
            log=log,
            progress=progress,
            extract_weight=extract_weight,
        )
        if err is not None:
            return err
        photos_extracted += pe
        bytes_written += pb

        _write_stamp(
            dest,
            remote=remote,
            repo=repo,
            tag=tag,
            record_count=n,
            project_root=project_root,
            applied_deltas=applied_deltas,
            local_photo_parts=local_photo_parts,
            photos_extracted=photos_extracted,
        )

        action = "updated" if existed else "downloaded"
        bits = [f"{n:,} records"]
        if deltas_applied:
            bits.append(f"{deltas_applied} delta(s)")
        if photos_extracted:
            bits.append(f"{photos_extracted:,} mugshots")
        msg = f"{'Updated' if existed else 'Downloaded'} database ({', '.join(bits)})"
        if not need_base and not deltas_applied and not photos_extracted:
            msg = "Local database is up to date"
            action = "skipped"
        progress.complete(msg)
        return SyncResult(
            ok=True,
            action=action,
            message=msg,
            record_count=n,
            sha256=(remote or {}).get("sha256"),
            bytes_written=bytes_written,
            photos_extracted=photos_extracted,
            deltas_applied=deltas_applied,
        )
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass
