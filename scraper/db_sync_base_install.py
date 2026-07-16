"""Install public base zip + stamp helpers for DB sync."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from scraper.db_sync_part1 import _log, _utc_now
from scraper.db_sync_part2 import _photo_fingerprint
from scraper.db_sync_preserve import apply_overlays_to_db, extract_local_overlays


def write_sync_stamp(
    dest: Path,
    *,
    remote: Optional[Dict[str, Any]],
    repo: str,
    tag: str,
    record_count: int,
    project_root: Path,
    applied_deltas: List[str],
    local_photo_parts: Dict[str, str],
    photos_extracted: int,
) -> None:
    stamp = {
        "format": 2,
        "remote_sha256": (remote or {}).get("sha256"),
        "base_id": (remote or {}).get("base_id"),
        "remote_record_count": (remote or {}).get("record_count") or record_count,
        "remote_photos_fingerprint": _photo_fingerprint(remote),
        "local_photo_parts": local_photo_parts,
        "applied_deltas": applied_deltas,
        "photos_extracted": photos_extracted,
        "synced_at_utc": _utc_now(),
        "repo": repo,
        "tag": tag,
        "local_record_count": record_count,
        "project_root": str(project_root),
    }
    dest.with_suffix(dest.suffix + ".sync.json").write_text(
        json.dumps(stamp, indent=2) + "\n", encoding="utf-8"
    )


def install_base_from_zip(
    zip_path: Path, dest: Path, log: Optional[Callable]
) -> int:
    """Extract arrests.db from zip, replace *dest*, restore local classifications."""
    extract_dir = zip_path.parent / "out"
    extract_dir.mkdir(exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        member = None
        for n in zf.namelist():
            if n.replace("\\", "/").endswith("arrests.db") and not n.endswith("/"):
                member = n
                break
        if not member:
            raise ValueError("Zip does not contain arrests.db")
        zf.extract(member, extract_dir)
        extracted = extract_dir / member
        if not extracted.is_file():
            candidates = list(extract_dir.rglob("arrests.db"))
            if not candidates:
                raise ValueError("Failed to extract arrests.db")
            extracted = candidates[0]
    conn = sqlite3.connect(str(extracted))
    n = int(conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0])
    conn.close()

    overlays: Dict[str, Dict[str, Any]] = {}
    if dest.is_file():
        try:
            overlays = extract_local_overlays(dest)
            if overlays:
                _log(
                    log,
                    f"Preserving {len(overlays):,} local ethnic classifications…",
                )
        except Exception as e:
            _log(log, f"Could not snapshot local classifications: {e}")
        bak = dest.with_suffix(
            dest.suffix + f".bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        )
        try:
            shutil.copy2(dest, bak)
            _log(log, f"Backed up previous DB → {bak.name}")
        except Exception as e:
            _log(log, f"Could not backup previous DB: {e}")

    tmp_dest = dest.with_suffix(dest.suffix + ".download")
    if tmp_dest.exists():
        tmp_dest.unlink()
    shutil.copy2(extracted, tmp_dest)
    try:
        from scraper.paths import clear_sqlite_sidecars

        clear_sqlite_sidecars(dest)
    except Exception:
        pass
    os.replace(str(tmp_dest), str(dest))
    if overlays:
        try:
            restored = apply_overlays_to_db(dest, overlays)
            _log(log, f"Restored {restored:,} local ethnic classifications")
        except Exception as e:
            _log(log, f"Could not restore local classifications: {e}")
    return n


def count_arrests(db_path: Path) -> Optional[int]:
    try:
        conn = sqlite3.connect(
            f"file:{Path(db_path).resolve().as_posix()}?mode=ro", uri=True
        )
        try:
            return int(conn.execute("SELECT COUNT(*) FROM arrests").fetchone()[0])
        finally:
            conn.close()
    except Exception:
        return None
