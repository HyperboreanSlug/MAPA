#!/usr/bin/env python3
"""Scrub local PII from arrests.db and package DB + referenced mugshots for release.

Outputs under ``releases/``:
  - arrests.db.zip              (SQLite only)
  - arrests.photos.NNN.zip      (mugshots under data/photos/)
  - MANIFEST.json               (sha256, sizes, photo part list)

Photo zips use path-hash shards (~50 MiB target) under GitHub's ~2 GiB limit.
Unchanged shards keep their SHA so clients re-download only dirty parts.
Only files referenced by ``arrests.photo_path`` are included.
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "data" / "arrests.db"
OUT_DIR = ROOT / "releases"
SCRUBBED = OUT_DIR / "arrests_scrubbed.db"
ZIP_PATH = OUT_DIR / "arrests.db.zip"
PHOTO_PREFIX = "arrests.photos."
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif"}

OUT_DIR.mkdir(exist_ok=True)

USER_PAT = re.compile(
    r"([A-Za-z]:[\\/]Users[\\/][^\\/\"']+[\\/])"
    r"|(/home/[^/\"']+/)"
    r"|(/Users/[^/\"']+/)",
    re.I,
)


def scrub_path(val: object) -> object:
    if not val:
        return val
    s = str(val)
    low = s.replace("/", "\\").lower()
    for marker in ("data\\photos\\", "data\\html\\", "data\\"):
        idx = low.find(marker)
        if idx >= 0:
            return s[idx:].replace("/", "\\")
    s2 = USER_PAT.sub("", s)
    s2 = re.sub(r"^[A-Za-z]:\\", "", s2)
    return s2


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _norm_rel(p: str) -> str:
    return (p or "").strip().replace("\\", "/").lstrip("./")


def collect_referenced_photos(db_path: Path) -> list[Path]:
    """Return absolute Paths for existing photo files referenced by the DB."""
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute(
            "SELECT DISTINCT photo_path FROM arrests "
            "WHERE photo_path IS NOT NULL AND TRIM(photo_path) != ''"
        ).fetchall()
    finally:
        conn.close()

    found: list[Path] = []
    missing = 0
    seen: set[str] = set()
    for (raw,) in rows:
        rel = _norm_rel(str(raw or ""))
        if not rel or rel in seen:
            continue
        seen.add(rel)
        parts = rel.lower().split("/")
        # Prefer dedicated mugshot trees under data/photos/
        if "photos" not in parts and not rel.lower().startswith("data/photos/"):
            missing += 1
            continue
        if any(p.endswith("_assets") or p == "assets" for p in parts):
            continue
        fp = (ROOT / rel).resolve()
        try:
            fp.relative_to(ROOT)
        except ValueError:
            missing += 1
            continue
        if not fp.is_file() or fp.suffix.lower() not in IMAGE_EXTS:
            missing += 1
            continue
        found.append(fp)
    print(f"photos: referenced_ok={len(found)} skipped_missing_or_non_photos={missing}")
    return sorted(found, key=lambda p: str(p).lower())


def write_photo_parts(files: list[Path], *, force_rebuild: bool = False) -> list[dict]:
    """Zip mugshots into stable path-hash photo parts (~50 MiB target)."""
    from scraper.db_publish_photos import write_photo_parts as _write

    return _write(ROOT, files, out_dir=OUT_DIR, force_rebuild=force_rebuild)


def scrub_database() -> int:
    if SCRUBBED.exists():
        SCRUBBED.unlink()
    shutil.copy2(SRC, SCRUBBED)

    conn = sqlite3.connect(str(SCRUBBED))
    conn.execute("PRAGMA journal_mode=DELETE")

    # Drop publisher-only / machine-local tables if present.
    for t in ("nsopw_query_log",):
        try:
            conn.execute(f"DROP TABLE IF EXISTS {t}")
        except Exception:
            pass

    cols = {r[1] for r in conn.execute("PRAGMA table_info(arrests)")}
    path_cols = [c for c in ("photo_path", "html_path", "raw_json") if c in cols]
    if not path_cols:
        conn.close()
        return 0

    cur = conn.execute(
        "SELECT id, " + ", ".join(path_cols) + " FROM arrests"
    )
    updates = []
    n_scrub = 0
    while True:
        batch = cur.fetchmany(5000)
        if not batch:
            break
        for row in batch:
            rid = row[0]
            values = list(row[1:])
            changed = False
            new_vals = []
            for col, val in zip(path_cols, values):
                if col in ("photo_path", "html_path") and val:
                    nv = scrub_path(val)
                    if nv != val:
                        changed = True
                    new_vals.append(nv)
                elif col == "raw_json" and val and re.search(
                    r"Users|C:\\\\|/home/", str(val)
                ):
                    try:
                        rdata = json.loads(val)

                        def walk(o):
                            if isinstance(o, dict):
                                return {k: walk(v) for k, v in o.items()}
                            if isinstance(o, list):
                                return [walk(v) for v in o]
                            if (
                                isinstance(o, str)
                                and re.search(r"Users|C:\\\\|/home/", o)
                                and not o.startswith("http")
                            ):
                                return scrub_path(o)
                            return o

                        nr = json.dumps(walk(rdata), ensure_ascii=False)[:50000]
                        if nr != val:
                            changed = True
                        new_vals.append(nr)
                    except Exception:
                        nr = USER_PAT.sub("", str(val))
                        if nr != val:
                            changed = True
                        new_vals.append(nr)
                else:
                    new_vals.append(val)
            if changed:
                n_scrub += 1
                updates.append(tuple(new_vals) + (rid,))

    print("rows_scrubbed", n_scrub)
    if updates:
        set_clause = ", ".join(f"{c}=?" for c in path_cols)
        conn.executemany(
            f"UPDATE arrests SET {set_clause} WHERE id=?",
            updates,
        )
    conn.commit()
    print("vacuum...")
    conn.execute("VACUUM")
    conn.close()
    return n_scrub


def main() -> int:
    import argparse
    import os

    ap = argparse.ArgumentParser(description="Scrub DB + package base/delta for release")
    ap.add_argument(
        "--full-base",
        action="store_true",
        help="Force a full arrests.db.zip base (clears delta chain)",
    )
    ap.add_argument(
        "--skip-photos",
        action="store_true",
        help="Reuse previous photo parts in MANIFEST (fast delta publishes)",
    )
    ap.add_argument(
        "--force-photo-rebuild",
        action="store_true",
        help="Rebuild every photo shard even if fingerprints match",
    )
    args = ap.parse_args()

    if not SRC.is_file():
        print(f"Missing {SRC}")
        return 1

    os.chdir(ROOT)

    print("scrubbing database…")
    scrub_database()

    c2 = sqlite3.connect(str(SCRUBBED))
    leaks = c2.execute(
        "SELECT COUNT(*) FROM arrests WHERE "
        "photo_path LIKE '%\\\\Users\\\\%' OR html_path LIKE '%\\\\Users\\\\%' OR "
        "photo_path LIKE '%/Users/%' OR html_path LIKE '%/Users/%' OR "
        "raw_json LIKE '%\\\\Users\\\\%' OR raw_json LIKE '%/Users/%'"
    ).fetchone()[0]
    c2.close()
    if leaks:
        print(f"WARN: path leak rows after scrub: {leaks}")

    photo_parts: list = []
    if args.skip_photos:
        man_path = OUT_DIR / "MANIFEST.json"
        if man_path.is_file():
            try:
                prev = json.loads(man_path.read_text(encoding="utf-8"))
                photo_parts = list(prev.get("photos") or [])
                print(f"skip-photos: reusing {len(photo_parts)} prior photo parts")
            except Exception:
                photo_parts = []
    else:
        files = collect_referenced_photos(SCRUBBED)
        photo_parts = write_photo_parts(
            files, force_rebuild=bool(args.force_photo_rebuild)
        )

    from scraper.db_publish_package import package_db_release

    result = package_db_release(
        ROOT,
        SCRUBBED,
        photo_parts=photo_parts,
        full_base=bool(args.full_base),
    )
    print(
        f"package mode={result.get('mode')} "
        f"records={result.get('record_count')} "
        f"ops={result.get('ops')} "
        f"photos={len(photo_parts)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
